from django.urls import path

from utterances.views import RoomUtteranceListCreateView, UtteranceDetailView

urlpatterns = [
    path(
        "rooms/<str:room_ref>/utterances/",
        RoomUtteranceListCreateView.as_view(),
        name="room-utterances",
    ),
    path("utterances/<int:utterance_id>/", UtteranceDetailView.as_view(), name="utterance-detail"),
]
