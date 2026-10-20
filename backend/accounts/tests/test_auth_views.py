import pytest
from django.core import mail

from accounts.models import Identity, PasswordResetToken

LOGIN_URL = "/api/auth/login/"
SIGNUP_URL = "/api/auth/signup/"
LOGOUT_URL = "/api/auth/logout/"
ME_URL = "/api/auth/user/"
CONFIG_URL = "/api/auth/config/"
CONFIRM_URL = "/api/auth/password-reset/confirm/"


@pytest.mark.django_db
class TestSignupView:
    def test_success_creates_user_and_returns_data(self, api_client):
        resp = api_client.post(SIGNUP_URL, {"email": "alice@example.com", "password": "StrongPass123!", "name": "Alice"})
        assert resp.status_code == 201
        assert resp.data["email"] == "alice@example.com"
        assert resp.data["name"] == "Alice"

    def test_weak_password_rejected(self, api_client):
        resp = api_client.post(SIGNUP_URL, {"email": "alice@example.com", "password": "short"})
        assert resp.status_code == 400
        assert "detail" in resp.data

    def test_numeric_password_rejected(self, api_client):
        resp = api_client.post(SIGNUP_URL, {"email": "alice@example.com", "password": "123456789012"})
        assert resp.status_code == 400

    def test_duplicate_email_rejected(self, api_client, make_user):
        make_user(email="dup@example.com")
        resp = api_client.post(SIGNUP_URL, {"email": "dup@example.com", "password": "StrongPass123!"})
        assert resp.status_code == 400

    def test_placeholder_is_not_claimed_by_signup(self, api_client, make_user):
        # An operator-created or invited account without a password must not
        # be taken over by whoever signs up with its address.
        placeholder = make_user(email="invited@example.com", password=None, name="")

        resp = api_client.post(
            SIGNUP_URL,
            {"email": "invited@example.com", "password": "StrongPass123!", "name": "Attacker"},
        )

        assert resp.status_code == 202
        assert "uid" not in resp.data
        placeholder.refresh_from_db()
        assert not placeholder.has_usable_password()
        assert placeholder.name == ""
        assert "_auth_user_id" not in api_client.session

        login_resp = api_client.post(
            LOGIN_URL, {"email": "invited@example.com", "password": "StrongPass123!"}
        )
        assert login_resp.status_code == 401

    def test_placeholder_owner_gets_setup_link(self, api_client, make_user):
        placeholder = make_user(email="invited@example.com", password=None)

        resp = api_client.post(
            SIGNUP_URL, {"email": "invited@example.com", "password": "StrongPass123!"}
        )

        assert resp.status_code == 202
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["invited@example.com"]
        token_obj = PasswordResetToken.objects.get(identity=placeholder)
        assert str(token_obj.token) in mail.outbox[0].body

        confirm = api_client.post(
            CONFIRM_URL, {"token": str(token_obj.token), "password": "OwnerPass456!"}
        )
        assert confirm.status_code == 200
        assert confirm.data["uid"] == placeholder.uid

        login_resp = api_client.post(
            LOGIN_URL, {"email": "invited@example.com", "password": "OwnerPass456!"}
        )
        assert login_resp.status_code == 200
        assert login_resp.data["uid"] == placeholder.uid

    def test_staff_placeholder_gets_setup_link(self, api_client, make_user):
        # Staff are claimed like anyone else: only through the emailed link.
        placeholder = make_user(email="staff@example.com", password=None, is_staff=True)

        resp = api_client.post(
            SIGNUP_URL, {"email": "staff@example.com", "password": "StrongPass123!"}
        )

        assert resp.status_code == 202
        assert len(mail.outbox) == 1
        placeholder.refresh_from_db()
        assert not placeholder.has_usable_password()

    def test_inactive_placeholder_gets_no_link(self, api_client, make_user):
        placeholder = make_user(email="gone@example.com", password=None, is_active=False)

        resp = api_client.post(
            SIGNUP_URL, {"email": "gone@example.com", "password": "StrongPass123!"}
        )

        # Same response as the active case, so it does not reveal the account's state.
        assert resp.status_code == 202
        assert len(mail.outbox) == 0
        assert not PasswordResetToken.objects.filter(identity=placeholder).exists()

    def test_signup_disabled_returns_403_and_creates_nothing(self, api_client, settings):
        settings.SIGNUP_ENABLED = False
        resp = api_client.post(
            SIGNUP_URL, {"email": "new@example.com", "password": "StrongPass123!"}
        )
        assert resp.status_code == 403
        assert not Identity.objects.filter(email="new@example.com").exists()

    def test_signup_disabled_does_not_send_setup_link(self, api_client, make_user, settings):
        settings.SIGNUP_ENABLED = False
        make_user(email="invited@example.com", password=None)
        resp = api_client.post(
            SIGNUP_URL, {"email": "invited@example.com", "password": "StrongPass123!"}
        )
        assert resp.status_code == 403
        assert len(mail.outbox) == 0

    def test_missing_email_rejected(self, api_client):
        resp = api_client.post(SIGNUP_URL, {"password": "StrongPass123!"})
        assert resp.status_code == 400

    def test_missing_password_rejected(self, api_client):
        resp = api_client.post(SIGNUP_URL, {"email": "alice@example.com"})
        assert resp.status_code == 400


@pytest.mark.django_db
class TestLoginView:
    def test_success_returns_user_data(self, api_client, make_user):
        make_user(email="login@example.com", password="TestPass123!")
        resp = api_client.post(LOGIN_URL, {"email": "login@example.com", "password": "TestPass123!"})
        assert resp.status_code == 200
        assert resp.data["email"] == "login@example.com"

    def test_wrong_password_returns_401(self, api_client, make_user):
        make_user(email="login2@example.com", password="TestPass123!")
        resp = api_client.post(LOGIN_URL, {"email": "login2@example.com", "password": "WrongPass999!"})
        assert resp.status_code == 401

    def test_nonexistent_user_returns_401(self, api_client):
        resp = api_client.post(LOGIN_URL, {"email": "ghost@example.com", "password": "TestPass123!"})
        assert resp.status_code == 401

    def test_email_case_insensitive(self, api_client, make_user):
        make_user(email="case@example.com", password="TestPass123!")
        resp = api_client.post(LOGIN_URL, {"email": "CASE@EXAMPLE.COM", "password": "TestPass123!"})
        assert resp.status_code == 200


@pytest.mark.django_db
class TestLogoutView:
    def test_authenticated_logout_succeeds(self, api_client, make_user):
        user = make_user()
        api_client.force_authenticate(user=user)
        resp = api_client.post(LOGOUT_URL)
        assert resp.status_code == 200

    def test_unauthenticated_logout_also_succeeds(self, api_client):
        # Logout is AllowAny — calling it unauthenticated is a no-op, not an error
        resp = api_client.post(LOGOUT_URL)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestMeView:
    def test_authenticated_returns_user_data(self, api_client, make_user):
        user = make_user(email="me@example.com", name="Me User")
        api_client.force_authenticate(user=user)
        resp = api_client.get(ME_URL)
        assert resp.status_code == 200
        assert resp.data["email"] == "me@example.com"
        assert resp.data["name"] == "Me User"
        assert "uid" in resp.data
        assert "is_staff" in resp.data

    def test_role_user(self, api_client, make_user):
        user = make_user(is_staff=False, is_superuser=False)
        api_client.force_authenticate(user=user)
        resp = api_client.get(ME_URL)
        assert resp.data["role"] == "user"

    def test_role_staff(self, api_client, make_user):
        user = make_user(is_staff=True, is_superuser=False)
        api_client.force_authenticate(user=user)
        resp = api_client.get(ME_URL)
        assert resp.data["role"] == "staff"

    def test_role_admin(self, api_client, make_user):
        user = make_user(is_staff=True, is_superuser=True)
        api_client.force_authenticate(user=user)
        resp = api_client.get(ME_URL)
        assert resp.data["role"] == "admin"

    def test_authenticated_includes_org_admin_flag(self, api_client, make_user, monkeypatch):
        user = make_user(email="me@example.com", name="Me User")
        api_client.force_authenticate(user=user)
        monkeypatch.setattr("accounts.views.has_org_admin_access", lambda user: True)
        resp = api_client.get(ME_URL)
        assert resp.status_code == 200
        assert resp.data["is_org_admin"] is True

    def test_can_view_surveys_flag(self, api_client, make_user, monkeypatch):
        monkeypatch.setattr("accounts.permissions.get_analytics_org_ids", lambda user: [])
        user = make_user(email="plain@example.com")
        api_client.force_authenticate(user=user)
        assert api_client.get(ME_URL).data["can_view_surveys"] is False

        monkeypatch.setattr("accounts.permissions.get_analytics_org_ids", lambda user: [1])
        assert api_client.get(ME_URL).data["can_view_surveys"] is True

        staff = make_user(email="staff@example.com", is_staff=True)
        api_client.force_authenticate(user=staff)
        monkeypatch.setattr("accounts.permissions.get_analytics_org_ids", lambda user: [])
        assert api_client.get(ME_URL).data["can_view_surveys"] is True

    def test_unauthenticated_returns_403(self, api_client):
        resp = api_client.get(ME_URL)
        assert resp.status_code == 403


@pytest.mark.django_db
class TestAuthConfigView:
    def test_reports_signup_enabled(self, api_client, settings):
        settings.SIGNUP_ENABLED = True
        assert api_client.get(CONFIG_URL).data == {"signup_enabled": True}

    def test_reports_signup_disabled(self, api_client, settings):
        settings.SIGNUP_ENABLED = False
        assert api_client.get(CONFIG_URL).data == {"signup_enabled": False}
