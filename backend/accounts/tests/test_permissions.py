"""Tests for IsPremiumOrStaff permission."""
import pytest
from unittest.mock import MagicMock
from accounts.models import UserProfile
from accounts.permissions import IsPremiumOrStaff


def _make_request(role):
    profile = MagicMock()
    profile.role = role
    profile.ROLE_PREMIUM = UserProfile.ROLE_PREMIUM
    profile.ROLE_STAFF = UserProfile.ROLE_STAFF
    user = MagicMock()
    user.profile = profile
    request = MagicMock()
    request.user = user
    return request


def test_user_role_denied():
    perm = IsPremiumOrStaff()
    assert perm.has_permission(_make_request(UserProfile.ROLE_USER), None) is False


def test_premium_role_allowed():
    perm = IsPremiumOrStaff()
    assert perm.has_permission(_make_request(UserProfile.ROLE_PREMIUM), None) is True


def test_staff_role_allowed():
    perm = IsPremiumOrStaff()
    assert perm.has_permission(_make_request(UserProfile.ROLE_STAFF), None) is True


def test_no_profile_denied():
    perm = IsPremiumOrStaff()
    request = MagicMock()
    request.user.profile = MagicMock(side_effect=UserProfile.DoesNotExist)
    type(request.user).profile = property(lambda self: (_ for _ in ()).throw(UserProfile.DoesNotExist()))
    assert perm.has_permission(request, None) is False
