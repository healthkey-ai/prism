"""Tests for the signup view — org required, UserProfile created."""
from unittest.mock import patch, MagicMock, call
from rest_framework.test import APIRequestFactory
from accounts.views import signup_view
from accounts.models import UserProfile


def _post(data):
    factory = APIRequestFactory()
    request = factory.post('/api/auth/signup/', data, format='json')
    request.session = MagicMock()
    return signup_view(request)


def test_signup_without_org_returns_400():
    response = _post({
        'email': 'test@example.com',
        'password': 'ValidPass123!',
        'name': 'Test User',
    })
    assert response.status_code == 400
    assert 'organization' in response.data['detail'].lower()


@patch('accounts.views.UserProfile.objects.create')
@patch('accounts.views.login')
@patch('accounts.views.get_token')
@patch('accounts.views.validate_password')
@patch('accounts.views.Identity.objects.create_user')
def test_signup_with_org_creates_profile(
    mock_create_user, mock_validate, mock_get_token, mock_login, mock_profile_create
):
    mock_user = MagicMock()
    mock_user.uid = 'test-uid'
    mock_user.email = 'newuser@example.com'
    mock_user.name = 'New User'
    mock_user.is_staff = False
    mock_profile = MagicMock()
    mock_profile.role = UserProfile.ROLE_USER
    mock_profile.organization = 'Test Hospital'
    mock_user.profile = mock_profile
    mock_create_user.return_value = mock_user

    response = _post({
        'email': 'newuser@example.com',
        'password': 'ValidPass123!',
        'name': 'New User',
        'organization': 'Test Hospital',
    })

    assert response.status_code == 201
    mock_profile_create.assert_called_once_with(
        user=mock_user, organization='Test Hospital', role=UserProfile.ROLE_USER
    )


@patch('accounts.views.UserProfile.objects.create')
@patch('accounts.views.login')
@patch('accounts.views.get_token')
@patch('accounts.views.validate_password')
@patch('accounts.views.Identity.objects.create_user')
def test_signup_response_includes_role_and_org(
    mock_create_user, mock_validate, mock_get_token, mock_login, mock_profile_create
):
    mock_user = MagicMock()
    mock_user.uid = 'uid-2'
    mock_user.email = 'org@example.com'
    mock_user.name = 'Org User'
    mock_user.is_staff = False
    mock_profile = MagicMock()
    mock_profile.role = UserProfile.ROLE_USER
    mock_profile.organization = 'City Medical'
    mock_user.profile = mock_profile
    mock_create_user.return_value = mock_user

    response = _post({
        'email': 'org@example.com',
        'password': 'ValidPass123!',
        'name': 'Org User',
        'organization': 'City Medical',
    })

    assert response.status_code == 201
    assert response.data['role'] == 'user'
    assert response.data['organization'] == 'City Medical'
