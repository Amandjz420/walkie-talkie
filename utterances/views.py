from rest_framework import generics, response, status
from rest_framework.views import APIView

from rooms.services import RoomService
from translations.serializers import TranslationFeedbackSerializer
from translations.models import TranslationFeedback
from utterances.serializers import UtteranceCreateSerializer, UtteranceSerializer
from utterances.services import UtteranceCreationService, UtteranceQueryService
from utterances.tasks import process_utterance_task


class RoomUtteranceListCreateView(APIView):
    def get(self, request, room_ref: str):
        room = RoomService.get_room_for_user(room_ref=room_ref, user=request.user)
        utterances = UtteranceQueryService.for_room(room)
        return response.Response(
            UtteranceSerializer(utterances, many=True, context={"request": request}).data
        )

    def post(self, request, room_ref: str):
        room = RoomService.get_room_for_user(room_ref=room_ref, user=request.user)
        serializer = UtteranceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        utterance = UtteranceCreationService.create_utterance(
            room=room,
            speaker=request.user,
            audio_file=serializer.validated_data["audio"],
            duration_ms=serializer.validated_data["duration_ms"],
        )
        process_utterance_task.delay(utterance.id)
        data = UtteranceSerializer(utterance, context={"request": request}).data
        return response.Response(data, status=status.HTTP_201_CREATED)


class UtteranceDetailView(APIView):
    def get(self, request, utterance_id: int):
        utterance = UtteranceQueryService.get_for_user(
            utterance_id=utterance_id,
            user=request.user,
        )
        return response.Response(UtteranceSerializer(utterance, context={"request": request}).data)


class TranslationFeedbackCreateView(generics.CreateAPIView):
    serializer_class = TranslationFeedbackSerializer

    def create(self, request, *args, **kwargs):
        utterance = UtteranceQueryService.get_for_user(
            utterance_id=kwargs["utterance_id"],
            user=request.user,
        )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        feedback = TranslationFeedback.objects.create(
            utterance=utterance,
            user=request.user,
            **serializer.validated_data,
        )
        return response.Response(
            TranslationFeedbackSerializer(feedback).data, status=status.HTTP_201_CREATED
        )
