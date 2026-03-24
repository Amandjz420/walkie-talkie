from django.conf import settings

from providers.base import SpeechToTextProvider, TextToSpeechProvider, TranslationProvider
from providers.elevenlabs import ElevenLabsTextToSpeechProvider, infer_elevenlabs_audio_extension
from providers.groq import GroqSpeechToTextProvider, GroqTranslationProvider
from providers.mock import MockSpeechToTextProvider, MockTextToSpeechProvider, MockTranslationProvider
from providers.sarvam import (
    SarvamSpeechToTextProvider,
    SarvamTextToSpeechProvider,
    SarvamTranslationProvider,
)


def get_stt_provider() -> SpeechToTextProvider:
    if settings.STT_PROVIDER == "mock":
        return MockSpeechToTextProvider()
    if settings.STT_PROVIDER == "groq":
        return GroqSpeechToTextProvider()
    if settings.STT_PROVIDER == "sarvam":
        return SarvamSpeechToTextProvider()
    raise ValueError(f"Unsupported STT provider: {settings.STT_PROVIDER}")


def get_translation_provider() -> TranslationProvider:
    if settings.TRANSLATION_PROVIDER == "mock":
        return MockTranslationProvider()
    if settings.TRANSLATION_PROVIDER == "groq":
        return GroqTranslationProvider()
    if settings.TRANSLATION_PROVIDER == "sarvam":
        return SarvamTranslationProvider()
    raise ValueError(f"Unsupported translation provider: {settings.TRANSLATION_PROVIDER}")


def get_tts_provider() -> TextToSpeechProvider:
    if settings.TTS_PROVIDER == "mock":
        return MockTextToSpeechProvider()
    if settings.TTS_PROVIDER == "elevenlabs":
        return ElevenLabsTextToSpeechProvider()
    if settings.TTS_PROVIDER == "sarvam":
        return SarvamTextToSpeechProvider()
    raise ValueError(f"Unsupported TTS provider: {settings.TTS_PROVIDER}")


def get_tts_storage_extension() -> str:
    if settings.TTS_PROVIDER == "elevenlabs":
        return infer_elevenlabs_audio_extension(settings.ELEVENLABS_TTS_OUTPUT_FORMAT)
    return "wav"
