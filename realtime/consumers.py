import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.http import Http404

from realtime.presence import RoomPresenceService
from realtime.services import RealtimeEventService
from rooms.services import RoomService
from rooms.models import RoomParticipant


class RoomConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        room_ref = self.scope["url_route"]["kwargs"]["room_ref"]
        if not user or isinstance(user, AnonymousUser) or user.is_anonymous:
            await self.close(code=4001)
            return
        room = await self.get_room(room_ref)
        if not room:
            await self.close(code=4404)
            return
        self.room_id = room.id
        self.user_id = user.id
        is_participant = await RoomParticipant.objects.filter(
            room_id=self.room_id, user_id=user.id
        ).aexists()
        if not is_participant:
            await self.close(code=4003)
            return
        self.group_name = RealtimeEventService.room_group_name(self.room_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        became_online = await self.mark_connected(self.room_id, self.user_id)
        if became_online:
            await self.broadcast_participant_online(self.room_id, self.user_id)

    async def disconnect(self, close_code):
        group_name = getattr(self, "group_name", None)
        if group_name:
            room_id = getattr(self, "room_id", None)
            user_id = getattr(self, "user_id", None)
            if room_id and user_id:
                became_offline = await self.mark_disconnected(room_id, user_id)
                if became_offline:
                    await self.broadcast_participant_offline(room_id, user_id)
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def room_event(self, event):
        await self.send(text_data=json.dumps(event["event"]))

    @database_sync_to_async
    def get_room(self, room_ref: str):
        try:
            return RoomService.get_room_by_reference(room_ref=room_ref)
        except Http404:
            return None

    @database_sync_to_async
    def mark_connected(self, room_id: int, user_id: int) -> bool:
        update = RoomPresenceService.mark_connected(room_id=room_id, user_id=user_id)
        return update.became_online

    @database_sync_to_async
    def mark_disconnected(self, room_id: int, user_id: int) -> bool:
        update = RoomPresenceService.mark_disconnected(room_id=room_id, user_id=user_id)
        return update.became_offline

    @database_sync_to_async
    def broadcast_participant_online(self, room_id: int, user_id: int) -> None:
        participant = RoomParticipant.objects.get(room_id=room_id, user_id=user_id)
        RealtimeEventService.broadcast_participant_joined(participant, presence_kind="online")

    @database_sync_to_async
    def broadcast_participant_offline(self, room_id: int, user_id: int) -> None:
        participant = RoomParticipant.objects.get(room_id=room_id, user_id=user_id)
        RealtimeEventService.broadcast_participant_left(participant)
