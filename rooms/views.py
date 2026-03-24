from rest_framework import generics, response, status
from rest_framework.views import APIView

from realtime.presence import RoomPresenceService
from rooms.serializers import (
    RoomCreateSerializer,
    RoomJoinSerializer,
    RoomParticipantSerializer,
    RoomPresenceSerializer,
    RoomSerializer,
)
from rooms.services import RoomService


class RoomCreateView(generics.CreateAPIView):
    serializer_class = RoomCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        room = RoomService.create_room(creator=request.user, **serializer.validated_data)
        data = RoomSerializer(room, context={"request": request}).data
        return response.Response(data, status=status.HTTP_201_CREATED)


class RoomDetailView(APIView):
    def get(self, request, room_ref: str):
        room = RoomService.get_room_for_user(room_ref=room_ref, user=request.user)
        return response.Response(RoomSerializer(room, context={"request": request}).data)


class RoomJoinView(APIView):
    def post(self, request, room_ref: str):
        serializer = RoomJoinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        room = RoomService.get_room_by_reference(room_ref=room_ref)
        if room.is_private and serializer.validated_data.get("code") != room.code:
            return response.Response(
                {"detail": "Room code is required to join this private room."},
                status=status.HTTP_403_FORBIDDEN,
            )
        participant = RoomService.join_room(room=room, user=request.user)
        return response.Response(
            RoomParticipantSerializer(participant, context={"request": request}).data
        )


class RoomParticipantsView(APIView):
    def get(self, request, room_ref: str):
        room = RoomService.get_room_for_user(room_ref=room_ref, user=request.user)
        participants = room.participants.select_related("user").order_by("joined_at")
        presence_map = RoomPresenceService.presence_map(room_id=room.id)
        return response.Response(
            RoomParticipantSerializer(
                participants,
                many=True,
                context={"request": request, "presence_map": presence_map},
            ).data
        )


class RoomPresenceView(APIView):
    def get(self, request, room_ref: str):
        room = RoomService.get_room_for_user(room_ref=room_ref, user=request.user)
        participants = list(room.participants.select_related("user").order_by("joined_at"))
        presence_map = RoomPresenceService.presence_map(room_id=room.id)
        online_user_ids = sorted(user_id for user_id, state in presence_map.items() if state.get("is_online"))
        data = RoomPresenceSerializer(
            {
                "room_id": room.id,
                "online_user_ids": online_user_ids,
                "participants": participants,
            },
            context={"request": request, "presence_map": presence_map},
        ).data
        return response.Response(data)
