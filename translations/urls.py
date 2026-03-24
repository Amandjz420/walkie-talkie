from django.urls import path

from utterances.views import TranslationFeedbackCreateView

urlpatterns = [
    path(
        "utterances/<int:utterance_id>/feedback/",
        TranslationFeedbackCreateView.as_view(),
        name="translation-feedback",
    ),
]
