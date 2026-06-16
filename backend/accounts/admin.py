from django.contrib import admin
from django.contrib.auth import get_user_model

from .models import UserProfile

Identity = get_user_model()


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display  = ["user_email", "user_name", "organization", "role"]
    list_editable = ["organization", "role"]
    list_filter   = ["role", "organization"]
    search_fields = ["user__email", "user__name", "organization"]
    list_select_related = ["user"]
    ordering = ["user__email"]

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = "Email"
    user_email.admin_order_field = "user__email"

    def user_name(self, obj):
        return obj.user.name
    user_name.short_description = "Name"
    user_name.admin_order_field = "user__name"

    @admin.action(description="Grant Premium role")
    def grant_premium(self, request, queryset):
        updated = queryset.update(role=UserProfile.ROLE_PREMIUM)
        self.message_user(request, f"Granted Premium to {updated} user(s).")

    @admin.action(description="Grant Staff role")
    def grant_staff(self, request, queryset):
        updated = queryset.update(role=UserProfile.ROLE_STAFF)
        self.message_user(request, f"Granted Staff to {updated} user(s).")

    @admin.action(description="Revoke to User role")
    def revoke_to_user(self, request, queryset):
        updated = queryset.update(role=UserProfile.ROLE_USER)
        self.message_user(request, f"Revoked {updated} user(s) to User role.")

    actions = ["grant_premium", "grant_staff", "revoke_to_user"]


@admin.register(Identity)
class IdentityAdmin(admin.ModelAdmin):
    """Read-only view of all identities — use UserProfile admin to manage roles/orgs."""
    list_display  = ["email", "name", "is_staff", "is_active", "created_at"]
    search_fields = ["email", "name", "uid"]
    list_filter   = ["is_staff", "is_active"]
    ordering      = ["email"]
    readonly_fields = ["uid", "issuer", "sub", "email", "name", "created_at",
                       "last_login", "is_active", "is_staff", "is_superuser"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
