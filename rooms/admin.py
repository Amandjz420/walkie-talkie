from django.contrib import admin

from rooms.models import Room, RoomParticipant


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "code", "created_by", "is_private", "created_at")
    search_fields = ("name", "code", "created_by__display_name")


@admin.register(RoomParticipant)
class RoomParticipantAdmin(admin.ModelAdmin):
    list_display = ("id", "room", "user", "joined_at")
    search_fields = ("room__name", "room__code", "user__display_name")
