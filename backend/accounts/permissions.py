from rest_framework.permissions import BasePermission


class IsPremiumOrStaff(BasePermission):
    """Allow access only to users with Premium or Staff analytics role."""
    message = "Premium subscription required."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        try:
            return request.user.profile.role in (
                request.user.profile.ROLE_PREMIUM,
                request.user.profile.ROLE_STAFF,
            )
        except Exception:
            return False
