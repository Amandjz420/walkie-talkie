import pytest
from rest_framework.test import APIClient

from rooms.services import RoomService
from users.models import User


@pytest.mark.django_db
def test_room_endpoints_accept_room_code_reference():
    user = User.objects.create(display_name="Speaker", email="speaker@example.com")
    room = RoomService.create_room(creator=user, name="Room", is_private=False)

    client = APIClient()
    client.credentials(HTTP_X_DEMO_USER_ID=str(user.id))

    room_response = client.get(f"/api/rooms/{room.code.lower()}/")
    participants_response = client.get(f"/api/rooms/{room.code.lower()}/participants/")

    assert room_response.status_code == 200
    assert room_response.data["id"] == room.id
    assert room_response.data["code"] == room.code
    assert participants_response.status_code == 200
    assert participants_response.data[0]["room_id"] == room.id


@pytest.mark.django_db
def test_room_create_defaults_is_private_to_false():
    user = User.objects.create(display_name="Speaker", email="speaker@example.com")
    client = APIClient()
    client.credentials(HTTP_X_DEMO_USER_ID=str(user.id))

    response = client.post("/api/rooms/", {"name": "New Room"}, format="json")

    assert response.status_code == 201
    assert response.data["name"] == "New Room"
    assert response.data["is_private"] is False
