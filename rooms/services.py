from django.db.models import Count, Q
from django.db import transaction
from django.http import Http404

from realtime.services import RealtimeEventService
from rooms.models import Room, RoomParticipant


class RoomService:
    @staticmethod
    def room_lookup_query(*, room_ref: str) -> Q:
        if str(room_ref).isdigit():
            return Q(id=int(room_ref)) | Q(code__iexact=str(room_ref))
        return Q(code__iexact=str(room_ref))

    @staticmethod
    @transaction.atomic
    def create_room(*, creator, name: str, is_private: bool = False) -> Room:
        room = Room.objects.create(name=name, created_by=creator, is_private=is_private)
        RoomParticipant.objects.create(room=room, user=creator)
        return room

    @staticmethod
    @transaction.atomic
    def join_room(*, room: Room, user) -> RoomParticipant:
        participant, created = RoomParticipant.objects.get_or_create(room=room, user=user)
        if created:
            transaction.on_commit(lambda: RealtimeEventService.broadcast_participant_joined(participant))
        return participant

    @staticmethod
    def get_room_by_reference(*, room_ref: str) -> Room:
        room = Room.objects.filter(RoomService.room_lookup_query(room_ref=room_ref)).first()
        if not room:
            raise Http404("Room not found.")
        return room

    @staticmethod
    def get_room_for_user(*, room_ref: str, user) -> Room:
        room = (
            Room.objects.annotate(participant_count=Count("participants"))
            .filter(RoomService.room_lookup_query(room_ref=room_ref), participants__user=user)
            .select_related("created_by")
            .first()
        )
        if not room:
            raise Http404("Room not found.")
        return room
