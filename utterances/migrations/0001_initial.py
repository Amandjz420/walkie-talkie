from django.conf import settings
from django.db import migrations, models

import utterances.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("rooms", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Utterance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_audio", models.FileField(upload_to=utterances.models.source_audio_upload_to)),
                ("source_language", models.CharField(blank=True, max_length=16, null=True)),
                ("original_transcript", models.TextField(blank=True)),
                ("duration_ms", models.PositiveIntegerField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("uploaded", "Uploaded"),
                            ("processing", "Processing"),
                            ("transcribed", "Transcribed"),
                            ("translated", "Translated"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="uploaded",
                        max_length=16,
                    ),
                ),
                ("error_message", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("room", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="utterances", to="rooms.room")),
                (
                    "speaker",
                    models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="utterances", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
