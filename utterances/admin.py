from django.contrib import admin

from utterances.models import Utterance


@admin.register(Utterance)
class UtteranceAdmin(admin.ModelAdmin):
    list_display = ("id", "room", "speaker", "status", "source_language", "created_at")
    list_filter = ("status", "source_language")
    search_fields = ("original_transcript", "speaker__display_name", "room__name")
