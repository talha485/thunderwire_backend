from django.urls import path
from .views import (
    RegisterView, LoginView, LogoutView,
    SendMessageView, MessageHistoryView,
    UserListView, StatusView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('messages/send/', SendMessageView.as_view(), name='messages-send'),
    path('messages/history/', MessageHistoryView.as_view(), name='messages-history'),
    path('users/list/', UserListView.as_view(), name='users-list'),
    path('status/', StatusView.as_view(), name='status'),
]
