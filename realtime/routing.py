from django.urls import path

from realtime.consumers import RoomConsumer

websocket_urlpatterns = [
    path("ws/rooms/<str:room_ref>/", RoomConsumer.as_asgi()),
]
