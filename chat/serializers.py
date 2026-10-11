from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Message


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']


class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    recipient = UserSerializer(read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'msg_id', 'sender', 'recipient', 'content', 'checksum', 'delivery_status', 'timestamp']
        read_only_fields = ['msg_id', 'checksum', 'delivery_status', 'timestamp']


class SendMessageSerializer(serializers.Serializer):
    recipient_id = serializers.IntegerField()
    content = serializers.CharField(max_length=4000, trim_whitespace=False)

    def validate_content(self, value):
        if not value.strip():
            raise serializers.ValidationError('message cannot be empty')
        return value

    def validate_recipient_id(self, value):
        try:
            return User.objects.get(pk=value, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError('recipient does not exist')
