from django.contrib.auth.models import User
from django.contrib.auth.hashers import check_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import Q
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from .models import Message, Session
from .serializers import UserSerializer, MessageSerializer, SendMessageSerializer
from .utils import crc32_hex

HISTORY_LIMIT = 50


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response({'error': 'username and password required'}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=username).exists():
            return Response({'error': 'username already taken'}, status=status.HTTP_400_BAD_REQUEST)

        # Runs AUTH_PASSWORD_VALIDATORS from settings (min length 8, not too
        # common, not all digits, not similar to the username).
        try:
            validate_password(password, user=User(username=username))
        except ValidationError as e:
            return Response({'error': ' '.join(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(username=username, password=password)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': 'invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active or not check_password(password, user.password):
            return Response({'error': 'invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        # housekeeping: drop this user's expired sessions
        Session.objects.filter(user=user, expires_at__lte=timezone.now()).delete()
        session = Session.objects.create(user=user)

        return Response({
            'token': str(session.token),
            'expires_at': session.expires_at,
            'user': UserSerializer(user).data,
        })


class LogoutView(APIView):
    def post(self, request):
        request.auth.delete()  # request.auth is the Session from SessionTokenAuthentication
        return Response(status=status.HTTP_204_NO_CONTENT)


class SendMessageView(APIView):
    """
    STUB: writes straight to Postgres. Later the UCP layer replaces the body
    of this view (send over UDP, wait for ACK, then update delivery_status).
    """
    def post(self, request):
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        content = serializer.validated_data['content']

        message = Message.objects.create(
            sender=request.user,
            recipient=serializer.validated_data['recipient_id'],
            content=content,
            checksum=crc32_hex(content),
            # no network hop yet, so a successful DB write counts as delivered
            delivery_status=Message.DeliveryStatus.ACKED,
        )
        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)


class MessageHistoryView(ListAPIView):
    """
    Last 50 messages involving the current user, oldest first.
    Optional ?with=<user_id> narrows it to one conversation.
    """
    serializer_class = MessageSerializer

    def get_queryset(self):
        me = self.request.user
        qs = Message.objects.select_related('sender', 'recipient')

        peer_id = self.request.query_params.get('with')
        if peer_id:
            if not peer_id.isdigit():
                return Message.objects.none()
            qs = qs.filter(
                Q(sender=me, recipient_id=peer_id) | Q(sender_id=peer_id, recipient=me)
            )
        else:
            qs = qs.filter(Q(sender=me) | Q(recipient=me))

        latest = list(qs.order_by('-timestamp')[:HISTORY_LIMIT])
        latest.reverse()
        return latest


class UserListView(ListAPIView):
    serializer_class = UserSerializer

    def get_queryset(self):
        return User.objects.filter(is_active=True).exclude(pk=self.request.user.pk).order_by('username')


class StatusView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            connection.ensure_connection()
            db_ok = True
        except Exception:
            db_ok = False

        return Response(
            {
                'status': 'ok' if db_ok else 'degraded',
                'database': 'up' if db_ok else 'down',
                'server_time': timezone.now(),
            },
            status=status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        )
