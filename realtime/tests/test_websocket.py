import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator

from config.asgi import application
from realtime.services import RealtimeEventService
from rooms.services import RoomService
from users.models import User


@sync_to_async
def create_user_and_room():
    user = User.objects.create(display_name="Speaker", email="speaker@example.com")
    room = RoomService.create_room(creator=user, name="Room", is_private=False)
    return user, room


@sync_to_async
def broadcast_processing_event(room_id: int):
    RealtimeEventService.broadcast_room_event(
        room_id=room_id,
        event_type="utterance.processing",
        payload={"utterance": {"id": 99, "status": "processing"}},
    )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_room_websocket_receives_broadcast():
    user, room = await create_user_and_room()
    communicator = WebsocketCommunicator(
        application,
        f"/ws/rooms/{room.code.lower()}/?user_id={user.id}",
    )

    connected, _ = await communicator.connect()

    assert connected is True

    await broadcast_processing_event(room.id)
    message = await communicator.receive_json_from()

    assert message["type"] == "utterance.processing"
    assert message["room_id"] == room.id
    assert "occurred_at" in message
    assert message["payload"]["utterance"]["status"] == "processing"

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_room_websocket_accepts_camel_case_user_id_query_param():
    user, room = await create_user_and_room()
    communicator = WebsocketCommunicator(
        application,
        f"/ws/rooms/{room.code.lower()}/?userId={user.id}",
    )

    connected, _ = await communicator.connect()

    assert connected is True

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_room_websocket_broadcasts_presence_joined_and_left():
    user_one, room = await create_user_and_room()

    @sync_to_async
    def create_second_user():
        user = User.objects.create(display_name="Listener", email="listener@example.com")
        RoomService.join_room(room=room, user=user)
        return user

    user_two = await create_second_user()
    communicator_one = WebsocketCommunicator(
        application,
        f"/ws/rooms/{room.code.lower()}/?user_id={user_one.id}",
    )
    communicator_two = WebsocketCommunicator(
        application,
        f"/ws/rooms/{room.code.lower()}/?user_id={user_two.id}",
    )

    connected_one, _ = await communicator_one.connect()
    assert connected_one is True
    own_join_event = await communicator_one.receive_json_from()
    assert own_join_event["type"] == "room.participant_joined"
    assert own_join_event["payload"]["participant"]["user_id"] == user_one.id
    assert own_join_event["payload"]["participant"]["is_online"] is True

    connected_two, _ = await communicator_two.connect()
    assert connected_two is True
    two_join_event = await communicator_one.receive_json_from()
    assert two_join_event["type"] == "room.participant_joined"
    assert two_join_event["payload"]["participant"]["user_id"] == user_two.id
    assert two_join_event["payload"]["participant"]["is_online"] is True

    await communicator_two.disconnect()
    left_event = await communicator_one.receive_json_from()
    assert left_event["type"] == "room.participant_left"
    assert left_event["payload"]["participant"]["user_id"] == user_two.id
    assert left_event["payload"]["participant"]["is_online"] is False

    await communicator_one.disconnect()
