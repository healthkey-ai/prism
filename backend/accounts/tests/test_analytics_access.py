"""Who may view an org's own aggregate results: get_analytics_org_ids and IsStaffOrOrgAnalyst."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from django.db import connection
from django.utils import timezone

from accounts.permissions import IsStaffOrOrgAnalyst, can_view_org_analytics
from accounts.promop_models import (
    PromopGroupAccess,
    PromopOrganization,
    PromopOrgTrust,
    PromopPatientGroup,
)
from accounts.utils import _promop_access_tables_available, get_analytics_org_ids

PROMOP_MODELS = [PromopOrganization, PromopOrgTrust, PromopPatientGroup, PromopGroupAccess]


@pytest.fixture(scope="module")
def promop_tables(django_db_setup, django_db_blocker):
    # Unmanaged PROMOP mirrors: create only their tables in the isolated test
    # database. Never use the shared DATABASE_URL here.
    with django_db_blocker.unblock():
        with connection.schema_editor() as editor:
            for model in PROMOP_MODELS:
                editor.create_model(model)
    _promop_access_tables_available.cache_clear()
    yield
    with django_db_blocker.unblock():
        with connection.schema_editor() as editor:
            for model in reversed(PROMOP_MODELS):
                editor.delete_model(model)
    _promop_access_tables_available.cache_clear()


@pytest.fixture
def orgs(promop_tables):
    return {
        "flf": PromopOrganization.objects.create(name="FLF", slug="flf"),
        "other": PromopOrganization.objects.create(name="Other", slug="other"),
        "closed": PromopOrganization.objects.create(name="Closed", slug="closed", is_active=False),
    }


def _grant(user, role, org=None, group=None, expires_at=None):
    return PromopGroupAccess.objects.create(
        identity=user, role=role, org=org, group=group, expires_at=expires_at,
    )


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["org_admin", "analyst"])
def test_org_admin_and_analyst_grants_count(make_user, orgs, role):
    user = make_user()
    _grant(user, role, org=orgs["flf"])
    assert get_analytics_org_ids(user) == [orgs["flf"].pk]


@pytest.mark.django_db
def test_other_roles_do_not_count(make_user, orgs):
    user = make_user()
    _grant(user, "doctor", org=orgs["flf"])
    assert get_analytics_org_ids(user) == []


@pytest.mark.django_db
def test_expired_grant_and_inactive_org_do_not_count(make_user, orgs):
    user = make_user()
    _grant(user, "analyst", org=orgs["flf"], expires_at=timezone.now() - timedelta(days=1))
    _grant(user, "org_admin", org=orgs["closed"])
    _grant(user, "analyst", org=orgs["other"], expires_at=timezone.now() + timedelta(days=1))
    assert get_analytics_org_ids(user) == [orgs["other"].pk]


@pytest.mark.django_db
def test_group_grant_does_not_open_the_whole_org(make_user, orgs):
    user = make_user()
    group = PromopPatientGroup.objects.create(organization=orgs["flf"])
    _grant(user, "analyst", group=group)
    assert get_analytics_org_ids(user) == []


@pytest.mark.django_db
def test_trust_and_public_visibility_do_not_count(make_user, orgs):
    # Seeing an org's patients through trust or public data does not make the
    # user one of its people.
    user = make_user(email="someone@trusted.org")
    PromopOrgTrust.objects.create(granting_org=orgs["flf"], trusted_domain="trusted.org")
    PromopOrganization.objects.filter(pk=orgs["other"].pk).update(allows_public_aggregated_data=True)
    assert get_analytics_org_ids(user) == []


@pytest.mark.django_db
def test_only_the_users_own_grants(make_user, orgs):
    user = make_user(email="a@example.com")
    colleague = make_user(email="b@example.com")
    _grant(colleague, "analyst", org=orgs["flf"])
    assert get_analytics_org_ids(user) == []
    assert get_analytics_org_ids(colleague) == [orgs["flf"].pk]


def _request(user):
    request = MagicMock()
    request.user = user
    return request


def test_permission_allows_staff_without_a_grant():
    staff = SimpleNamespace(is_authenticated=True, is_staff=True)
    assert IsStaffOrOrgAnalyst().has_permission(_request(staff), None) is True


def test_permission_refuses_anonymous_and_users_without_a_grant(monkeypatch):
    monkeypatch.setattr("accounts.permissions.get_analytics_org_ids", lambda user: [])
    plain = SimpleNamespace(is_authenticated=True, is_staff=False)
    anonymous = SimpleNamespace(is_authenticated=False, is_staff=False)
    assert IsStaffOrOrgAnalyst().has_permission(_request(plain), None) is False
    assert IsStaffOrOrgAnalyst().has_permission(_request(anonymous), None) is False
    assert can_view_org_analytics(None) is False


def test_permission_allows_an_org_analyst(monkeypatch):
    monkeypatch.setattr("accounts.permissions.get_analytics_org_ids", lambda user: [7])
    analyst = SimpleNamespace(is_authenticated=True, is_staff=False)
    assert IsStaffOrOrgAnalyst().has_permission(_request(analyst), None) is True
