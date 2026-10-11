from django.contrib import admin
from .models import Message, Session


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['msg_id', 'sender', 'recipient', 'delivery_status', 'timestamp']
    list_filter = ['delivery_status']


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'created_at', 'expires_at']
