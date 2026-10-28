import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import F
from django.middleware.csrf import get_token
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework import status

LOCKOUT_THRESHOLD = 10

logger = logging.getLogger(__name__)

from .models import Identity, Organization, PasswordResetToken
from .utils import has_org_admin_access


class _EmailAlreadyExists(Exception):
    """Raised when a local account with a usable password already exists for this email."""


class _ExistingAccountNeedsSetup(Exception):
    """Raised when a local account exists for this email but has no password yet.

    Sign-up never sets that account's password itself: nothing in the request
    proves the caller owns the address, and the account may already carry
    roles, group access or patient data. The owner finishes setting it
    up through a single-use link sent to the address instead.
    """

    def __init__(self, identity):
        super().__init__()
        self.identity = identity


# Same text whether or not a link was actually sent, so the response does not
# reveal whether the account behind the address is active.
_SETUP_LINK_SENT_DETAIL = (
    "An account already exists for this email. If it can be set up here, "
    "we have sent a link to that address to finish setting it up."
)


def _create_signup_identity(email, password, name):
    local_identities = list(
        Identity.objects.select_for_update()
        .filter(email__iexact=email, issuer="urn:local")
        .order_by("id")
    )

    for identity in local_identities:
        if identity.has_usable_password():
            raise _EmailAlreadyExists

    if local_identities:
        raise _ExistingAccountNeedsSetup(local_identities[0])

    return Identity.objects.create_user(email=email, password=password, name=name)


def _send_password_link(identity, subject, intro):
    token_obj = PasswordResetToken.objects.create(identity=identity)
    link = f"{settings.FRONTEND_URL}?token={token_obj.token}"
    try:
        send_mail(
            subject=subject,
            message=(
                f"Hi {identity.name or identity.email},\n\n"
                f"{intro} This link expires in 1 hour.\n\n"
                f"{link}\n\n"
                f"If you did not request this, you can ignore this email.\n"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[identity.email],
        )
    except Exception:
        logger.exception("Failed to send password email to %s", identity.email[:3] + "***")


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
def login_view(request):
    email = request.data.get("email", "")
    password = request.data.get("password", "")

    # Per-account lockout check — look up by email before calling authenticate().
    identity = Identity.objects.filter(email__iexact=email).first()
    if identity is not None and identity.locked_until is not None:
        if identity.locked_until > timezone.now():
            return Response(
                {"detail": f"Account locked. Try again after {identity.locked_until.isoformat()}."},
                status=status.HTTP_403_FORBIDDEN,
            )

    user = authenticate(request, username=email, password=password)

    if user is None:
        # Increment failed_login_count race-safely; lock if threshold reached.
        if identity is not None:
            new_count = identity.failed_login_count + 1
            if new_count >= LOCKOUT_THRESHOLD:
                Identity.objects.filter(pk=identity.pk).update(
                    failed_login_count=F("failed_login_count") + 1,
                    locked_until=timezone.now() + timedelta(minutes=15),
                )
            else:
                Identity.objects.filter(pk=identity.pk).update(
                    failed_login_count=F("failed_login_count") + 1,
                )
        return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

    # Successful login — reset lockout state.
    Identity.objects.filter(pk=user.pk).update(failed_login_count=0, locked_until=None)

    request.session.cycle_key()
    login(request, user)
    get_token(request)
    return Response(_user_data(user))


@api_view(["POST"])
@permission_classes([AllowAny])
def logout_view(request):
    logout(request)
    return Response({"detail": "Logged out."})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
def signup_view(request):
    if not settings.SIGNUP_ENABLED:
        return Response(
            {"detail": "Sign-up is disabled. Ask an administrator for an account."},
            status=status.HTTP_403_FORBIDDEN,
        )

    email    = request.data.get("email", "").strip()
    password = request.data.get("password", "")
    name     = request.data.get("name", "").strip()

    if not email or not password:
        return Response({"detail": "Email and password are required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        validate_password(password)
    except DjangoValidationError as exc:
        return Response({"detail": " ".join(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic():
            user = _create_signup_identity(email, password, name)
    except _ExistingAccountNeedsSetup as exc:
        identity = exc.identity
        if identity.is_active:
            _send_password_link(
                identity,
                subject="Finish setting up your PRism account",
                intro="Click the link below to choose a password for your account.",
            )
        else:
            logger.warning("Sign-up for inactive account %s; no link sent", identity.uid)
        return Response({"detail": _SETUP_LINK_SENT_DETAIL}, status=status.HTTP_202_ACCEPTED)
    except _EmailAlreadyExists:
        return Response({"detail": "An account with this email already exists."}, status=status.HTTP_400_BAD_REQUEST)
    except IntegrityError:
        # DB-level uniqueness violation (e.g. uid collision or a unique constraint on email)
        return Response({"detail": "An account with this email already exists."}, status=status.HTTP_400_BAD_REQUEST)

    request.session.cycle_key()
    login(request, user, backend="accounts.backends.EmailBackend")
    get_token(request)
    return Response(_user_data(user), status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_view(request):
    get_token(request)
    return Response(_user_data(request.user))


@api_view(["GET"])
@permission_classes([AllowAny])
def auth_config_view(request):
    """Public settings the login page needs before anyone is signed in."""
    return Response({"signup_enabled": settings.SIGNUP_ENABLED})


@api_view(["GET"])
@permission_classes([AllowAny])
def organizations_view(request):
    """Return alphabetical org names from the Organization table for the signup dropdown."""
    orgs = list(Organization.objects.values_list("name", flat=True))
    return Response(orgs)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_orgs_view(request):
    """Return org options visible to the current user.

    Staff: all distinct orgs present in PatientInfo.
    Others: their own org plus any org that has granted trust to their org
            (or email domain) via PROMOP's OrgTrust table.
    """
    from patients.models import PatientInfo
    from accounts.utils import get_visible_org_names

    if request.user.is_staff:
        orgs = (
            PatientInfo.objects
            .exclude(organization__isnull=True)
            .values_list("organization__name", flat=True)
            .distinct()
            .order_by("organization__name")
        )
        return Response([{"value": o, "label": o} for o in orgs])

    visible = get_visible_org_names(request.user)
    return Response([{"value": o, "label": o} for o in visible])


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
def password_reset_request_view(request):
    email = request.data.get("email", "").strip()
    if not email:
        return Response({"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

    # Always return 200 — never reveal whether the email exists
    try:
        identity = Identity.objects.get(email__iexact=email, issuer="urn:local")
    except Identity.DoesNotExist:
        return Response({"detail": "If that email is registered you will receive a reset link shortly."})

    _send_password_link(
        identity,
        subject="Reset your PRism password",
        intro="Click the link below to reset your password.",
    )
    return Response({"detail": "If that email is registered you will receive a reset link shortly."})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
def password_reset_confirm_view(request):
    token_str = request.data.get("token", "").strip()
    password = request.data.get("password", "")

    if not token_str or not password:
        return Response({"detail": "Token and password are required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        token_obj = PasswordResetToken.objects.select_related("identity").get(token=token_str)
    except (PasswordResetToken.DoesNotExist, ValueError):
        return Response({"detail": "Invalid or expired reset link."}, status=status.HTTP_400_BAD_REQUEST)

    if not token_obj.is_valid():
        return Response({"detail": "This reset link has expired or has already been used."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        validate_password(password, token_obj.identity)
    except DjangoValidationError as exc:
        return Response({"detail": " ".join(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

    token_obj.identity.set_password(password)
    token_obj.identity.save(update_fields=["password"])
    # Every outstanding link for this account dies with the one that was used.
    PasswordResetToken.objects.filter(
        identity=token_obj.identity, used_at__isnull=True
    ).update(used_at=timezone.now())

    request.session.cycle_key()
    login(request, token_obj.identity, backend="accounts.backends.EmailBackend")
    get_token(request)
    return Response(_user_data(token_obj.identity))


def _user_data(user):
    is_premium = getattr(user, "is_premium", False)
    is_org_admin = has_org_admin_access(user)
    return {
        "uid":        user.uid,
        "email":      user.email,
        "name":       user.name,
        "is_staff":   user.is_staff,
        "is_premium": is_premium,
        "is_org_admin": is_org_admin,
        "role":       "admin" if user.is_superuser else "staff" if user.is_staff else "user",
    }
