from rest_framework.permissions import BasePermission


class IsRoomParticipant(BasePermission):
    message = "You must be a participant in this room."

    def has_object_permission(self, request, view, obj) -> bool:
        room = getattr(obj, "room", obj)
        return room.participants.filter(user=request.user).exists()
