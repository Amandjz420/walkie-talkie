import pytest
from django.db import IntegrityError

from rooms.models import RoomParticipant
from users.models import User
from rooms.services import RoomService


@pytest.mark.django_db
def test_room_participant_unique_constraint():
    creator = User.objects.create(display_name="Creator", email="creator@example.com")
    room = RoomService.create_room(creator=creator, name="Room", is_private=False)

    with pytest.raises(IntegrityError):
        RoomParticipant.objects.create(room=room, user=creator)
