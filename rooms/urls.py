from django.urls import path

from rooms.views import RoomCreateView, RoomDetailView, RoomJoinView, RoomParticipantsView, RoomPresenceView

urlpatterns = [
    path("rooms/", RoomCreateView.as_view(), name="room-create"),
    path("rooms/<str:room_ref>/join/", RoomJoinView.as_view(), name="room-join"),
    path(
        "rooms/<str:room_ref>/participants/",
        RoomParticipantsView.as_view(),
        name="room-participants",
    ),
    path("rooms/<str:room_ref>/presence/", RoomPresenceView.as_view(), name="room-presence"),
    path("rooms/<str:room_ref>/", RoomDetailView.as_view(), name="room-detail"),
]
