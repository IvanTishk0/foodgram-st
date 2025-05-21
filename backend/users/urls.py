from django.urls import path
from .views import ( CurrentUserView, UserAvatarUpdateView, 
    SetPasswordView, CustomAuthToken, LogoutView, SubscriptionListView, SubscribeView, UserDetailView, UserListCreateView, ResetPasswordView
)

urlpatterns = [
    path('users/', UserListCreateView.as_view(), name='user-list-create'),
    path('users/me/', CurrentUserView.as_view(), name='user-me'),
    path('users/me/avatar/', UserAvatarUpdateView.as_view(), name='user-avatar'),
    path('users/reset_password/', ResetPasswordView.as_view(), name='user-reset-password'),
    path('users/set_password/', SetPasswordView.as_view(), name='user-set-password'),
    path('auth/token/login/', CustomAuthToken.as_view(), name='token-login'),
    path('auth/token/logout/', LogoutView.as_view(), name='token-logout'),
    path('users/subscriptions/', SubscriptionListView.as_view(), name='user-subscriptions'),
    path('users/<int:id>/subscribe/', SubscribeView.as_view(), name='user-subscribe'),
    path('users/<int:pk>/', UserDetailView.as_view(), name='user-detail'),
] 