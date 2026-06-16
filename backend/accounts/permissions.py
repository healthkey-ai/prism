from rest_framework.permissions import BasePermission

from accounts.models import UserProfile


class IsPremiumOrStaff(BasePermission):
    """Allow access only to users with Premium or Staff analytics role."""
    message = "Premium subscription required."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        try:
            return request.user.profile.role in (
                UserProfile.ROLE_PREMIUM,
                UserProfile.ROLE_STAFF,
            )
        except (UserProfile.DoesNotExist, AttributeError):
            return False
