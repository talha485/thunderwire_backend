import uuid
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from .models import Session


class SessionTokenAuthentication(BaseAuthentication):
    """
    Expects the header:  Authorization: Bearer <uuid4 token>
    Tokens come from POST /api/login/ and expire after 24h.
    """
    keyword = 'Bearer'

    def authenticate(self, request):
        parts = get_authorization_header(request).split()

        if not parts or parts[0].lower() != self.keyword.lower().encode():
            return None  # no token sent -> let permission classes decide

        if len(parts) != 2:
            raise AuthenticationFailed('invalid authorization header')

        try:
            token = uuid.UUID(parts[1].decode())
        except (ValueError, UnicodeDecodeError):
            raise AuthenticationFailed('invalid token')

        try:
            session = Session.objects.select_related('user').get(token=token)
        except Session.DoesNotExist:
            raise AuthenticationFailed('invalid token')

        if session.expires_at <= timezone.now():
            session.delete()
            raise AuthenticationFailed('token expired')

        if not session.user.is_active:
            raise AuthenticationFailed('user inactive')

        return (session.user, session)

    def authenticate_header(self, request):
        # makes DRF return 401 (not 403) when auth is missing/invalid
        return self.keyword
