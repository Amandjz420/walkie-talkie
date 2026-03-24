import pytest
from rest_framework.test import APIClient

from common.choices import InputLanguageMode
from users.models import User


@pytest.mark.django_db
def test_me_preferences_returns_full_user_payload():
    user = User.objects.create(
        display_name="Speaker",
        email="speaker@example.com",
        preferred_output_language="en",
    )
    client = APIClient()
    client.credentials(HTTP_X_DEMO_USER_ID=str(user.id))

    response = client.patch(
        "/api/me/preferences/",
        {
            "display_name": "Updated Speaker",
            "preferred_output_language": "es",
            "input_language_mode": InputLanguageMode.MANUAL,
            "manual_input_language": "fr",
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data["id"] == user.id
    assert response.data["display_name"] == "Updated Speaker"
    assert response.data["preferred_output_language"] == "es"
    assert response.data["effective_input_language"] == "fr"
    assert response.data["is_demo_user"] is False
