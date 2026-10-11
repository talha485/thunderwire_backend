import uuid
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

SESSION_LIFETIME = timedelta(hours=24)


class Message(models.Model):
    class DeliveryStatus(models.IntegerChoices):
        PENDING = 0, 'pending'
        ACKED = 1, 'acked'
        FAILED = 2, 'delivery_failed'  # UCP: no ACK after 3 retries

    msg_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE)
    recipient = models.ForeignKey(User, related_name='received_messages', on_delete=models.CASCADE)
    content = models.TextField()
    checksum = models.CharField(max_length=16)
    delivery_status = models.IntegerField(choices=DeliveryStatus.choices, default=DeliveryStatus.PENDING)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.sender} - {self.recipient} - {self.timestamp}'


def default_expiry():
    return timezone.now() + SESSION_LIFETIME


class Session(models.Model):
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(User, related_name='auth_sessions', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=default_expiry)

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    def __str__(self):
        return f'{self.user} - expires {self.expires_at}'
