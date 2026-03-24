from rest_framework import serializers

from rooms.models import Room, RoomParticipant
from users.serializers import UserSerializer


class RoomSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    participant_count = serializers.SerializerMethodField()
    created_by_id = serializers.IntegerField(source="created_by.id", read_only=True)
    created_by_name = serializers.CharField(source="created_by.display_name", read_only=True)
    is_participant = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = (
            "id",
            "name",
            "code",
            "created_by",
            "created_by_id",
            "created_by_name",
            "is_private",
            "participant_count",
            "is_participant",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "code", "created_at", "updated_at")

    def get_participant_count(self, obj):
        return getattr(obj, "participant_count", None) or obj.participants.count()

    def get_is_participant(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return obj.participants.filter(user=user).exists()


class RoomCreateSerializer(serializers.ModelSerializer):
    is_private = serializers.BooleanField(required=False, default=False)

    class Meta:
        model = Room
        fields = ("name", "is_private")


class RoomJoinSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=12, required=False)


class RoomParticipantSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    room_id = serializers.IntegerField(source="room.id", read_only=True)
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    display_name = serializers.CharField(source="user.display_name", read_only=True)
    preferred_output_language = serializers.CharField(
        source="user.preferred_output_language", read_only=True
    )
    is_current_user = serializers.SerializerMethodField()
    is_online = serializers.SerializerMethodField()
    last_seen_at = serializers.SerializerMethodField()

    class Meta:
        model = RoomParticipant
        fields = (
            "id",
            "room_id",
            "user_id",
            "display_name",
            "preferred_output_language",
            "is_current_user",
            "is_online",
            "last_seen_at",
            "user",
            "joined_at",
        )

    def get_is_current_user(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and user.id == obj.user_id)

    def get_is_online(self, obj):
        presence = self._get_presence(obj)
        return presence.get("is_online", False)

    def get_last_seen_at(self, obj):
        presence = self._get_presence(obj)
        last_seen_at = presence.get("last_seen_at")
        return last_seen_at.isoformat().replace("+00:00", "Z") if last_seen_at else None

    def _get_presence(self, obj):
        presence_map = self.context.get("presence_map") or {}
        return presence_map.get(obj.user_id, {})


class RoomPresenceSerializer(serializers.Serializer):
    room_id = serializers.IntegerField()
    online_user_ids = serializers.ListField(child=serializers.IntegerField())
    participants = RoomParticipantSerializer(many=True)
