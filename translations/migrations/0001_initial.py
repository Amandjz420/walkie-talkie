from django.conf import settings
from django.db import migrations, models

import translations.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("utterances", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="UtteranceTranslation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("target_language", models.CharField(max_length=16)),
                ("translated_text", models.TextField()),
                ("tts_audio", models.FileField(upload_to=translations.models.tts_audio_upload_to)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "utterance",
                    models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="translations", to="utterances.utterance"),
                ),
            ],
        ),
        migrations.CreateModel(
            name="TranslationFeedback",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reason", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "utterance",
                    models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="feedback_items", to="utterances.utterance"),
                ),
                (
                    "user",
                    models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="translation_feedback", to=settings.AUTH_USER_MODEL),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="utterancetranslation",
            constraint=models.UniqueConstraint(fields=("utterance", "target_language"), name="unique_utterance_translation"),
        ),
    ]
