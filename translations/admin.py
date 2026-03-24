from django.contrib import admin

from translations.models import TranslationFeedback, UtteranceTranslation


@admin.register(UtteranceTranslation)
class UtteranceTranslationAdmin(admin.ModelAdmin):
    list_display = ("id", "utterance", "target_language", "created_at")
    search_fields = ("translated_text", "target_language")


@admin.register(TranslationFeedback)
class TranslationFeedbackAdmin(admin.ModelAdmin):
    list_display = ("id", "utterance", "user", "created_at")
    search_fields = ("user__display_name", "reason")
