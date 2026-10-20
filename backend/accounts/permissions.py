from rest_framework.permissions import BasePermission
from .utils import get_analytics_org_ids, has_org_admin_access


class IsPremiumOrStaff(BasePermission):
    """Allow access only to users with Premium access or staff status.

    Premium is managed in PRomop (Identity.is_premium) and is readable here
    because PRism and PRomop share the same PostgreSQL database and Identity table.
    """
    message = "Premium subscription required."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return (
            getattr(request.user, "is_premium", False)
            or request.user.is_staff
            or getattr(request.user, "is_superuser", False)
            or has_org_admin_access(request.user)
        )


def can_view_org_analytics(user) -> bool:
    """Staff, or an org_admin or analyst of at least one org."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return getattr(user, "is_staff", False) is True or bool(get_analytics_org_ids(user))


class IsStaffOrOrgAnalyst(BasePermission):
    """Allow staff, and org_admin or analyst users of at least one org.

    This only decides whether the user may use the endpoint at all; the view
    still limits what they see to their own orgs (get_analytics_org_ids).
    """
    message = "Organisation admin or analyst access required."

    def has_permission(self, request, view):
        return can_view_org_analytics(request.user)
