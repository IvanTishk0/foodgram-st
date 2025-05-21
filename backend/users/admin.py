from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Follow

User = get_user_model()


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    search_fields = ('email', 'username')
    list_display = (
        'id',
        'username',
        'email',
        'first_name',
        'last_name',
        'is_staff'
    )


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ('user', 'author')
    search_fields = ('user__username', 'author__username')
