"""Tests for org-scoping in metrics view (_apply_org_scope helper)."""
import pytest
from unittest.mock import MagicMock, patch
from rest_framework.response import Response
from accounts.models import UserProfile
from accounts.utils import apply_org_scope as _apply_org_scope


def _make_user(role, organization='Org A', has_profile=True):
    user = MagicMock()
    if has_profile:
        profile = MagicMock()
        profile.role = role
        profile.organization = organization
        user.profile = profile
    else:
        type(user).profile = property(lambda self: (_ for _ in ()).throw(UserProfile.DoesNotExist()))
    return user


def _make_qs():
    qs = MagicMock()
    qs.filter.return_value = qs
    return qs


def test_staff_sees_all_orgs():
    qs = _make_qs()
    user = _make_user(UserProfile.ROLE_STAFF)
    scoped_qs, err = _apply_org_scope(qs, user)
    assert err is None
    qs.filter.assert_not_called()
    assert scoped_qs is qs


@patch('accounts.utils.get_visible_org_names', return_value=['Org A'])
def test_user_role_scoped_to_org(mock_visible):
    qs = _make_qs()
    user = _make_user(UserProfile.ROLE_USER, organization='Org A')
    scoped_qs, err = _apply_org_scope(qs, user)
    assert err is None
    qs.filter.assert_called_once_with(organization__in=['Org A'])


def test_user_with_no_org_returns_403():
    qs = _make_qs()
    user = _make_user(UserProfile.ROLE_USER, organization='')
    scoped_qs, err = _apply_org_scope(qs, user)
    assert scoped_qs is None
    assert err is not None
    assert err.status_code == 403


def test_no_profile_returns_403():
    qs = _make_qs()
    user = _make_user(None, has_profile=False)
    scoped_qs, err = _apply_org_scope(qs, user)
    assert scoped_qs is None
    assert err is not None
    assert err.status_code == 403


@patch('accounts.utils.get_visible_org_names', return_value=['Cancer Center'])
def test_premium_role_scoped_to_org(mock_visible):
    qs = _make_qs()
    user = _make_user(UserProfile.ROLE_PREMIUM, organization='Cancer Center')
    scoped_qs, err = _apply_org_scope(qs, user)
    assert err is None
    qs.filter.assert_called_once_with(organization__in=['Cancer Center'])


@patch('accounts.utils.get_visible_org_names', return_value=['HealthTree Trust', 'Hospital A', 'Hospital B'])
def test_multi_org_trust_scoped_to_all_visible(mock_visible):
    """A trusted org user gets data filtered to all their accessible orgs."""
    qs = _make_qs()
    user = _make_user(UserProfile.ROLE_USER, organization='HealthTree Trust')
    scoped_qs, err = _apply_org_scope(qs, user)
    assert err is None
    qs.filter.assert_called_once_with(
        organization__in=['HealthTree Trust', 'Hospital A', 'Hospital B']
    )
