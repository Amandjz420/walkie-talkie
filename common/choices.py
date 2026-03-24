from django.db import models


class InputLanguageMode(models.TextChoices):
    AUTO = "auto", "Auto"
    MANUAL = "manual", "Manual"


class UtteranceStatus(models.TextChoices):
    UPLOADED = "uploaded", "Uploaded"
    PROCESSING = "processing", "Processing"
    TRANSCRIBED = "transcribed", "Transcribed"
    TRANSLATED = "translated", "Translated"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
