import pytest

from providers.base import ProviderConfigurationError, ProviderError
from providers.elevenlabs import (
    ElevenLabsTextToSpeechProvider,
    infer_elevenlabs_audio_extension,
)


class FakeTextToSpeechAPI:
    def convert(self, *, voice_id, output_format, text, model_id, language_code):
        assert voice_id == "voice_123"
        assert output_format == "mp3_44100_128"
        assert model_id == "eleven_flash_v2_5"
        assert language_code == "hi"
        assert text == "नमस्ते"
        return [b"audio", b"-bytes"]


class FakeElevenLabsClient:
    text_to_speech = FakeTextToSpeechAPI()


class FakeApiError(Exception):
    def __init__(self, *, status_code, body):
        super().__init__("api error")
        self.status_code = status_code
        self.body = body


class FlakyStream:
    def __init__(self, fail: bool):
        self.fail = fail

    def __iter__(self):
        if self.fail:
            raise FakeApiError(
                status_code=409,
                body={
                    "detail": {
                        "code": "already_running",
                        "message": "Multiple voice additions/deletions for the same voice were called at the same time. Please retry shortly.",
                    }
                },
            )
        yield b"retry"
        yield b"-ok"


class FlakyTextToSpeechAPI:
    def __init__(self):
        self.calls = 0

    def convert(self, *, voice_id, output_format, text, model_id, language_code):
        self.calls += 1
        return FlakyStream(fail=self.calls == 1)


class FlakyElevenLabsClient:
    def __init__(self):
        self.text_to_speech = FlakyTextToSpeechAPI()


@pytest.mark.django_db
def test_elevenlabs_tts_returns_audio_bytes(monkeypatch, settings):
    settings.ELEVENLABS_TTS_VOICE_ID = "voice_123"
    settings.ELEVENLABS_TTS_OUTPUT_FORMAT = "mp3_44100_128"
    settings.ELEVENLABS_TTS_MODEL = "eleven_flash_v2_5"
    monkeypatch.setattr("providers.elevenlabs.get_elevenlabs_client", lambda: FakeElevenLabsClient())

    audio = ElevenLabsTextToSpeechProvider().synthesize(text="नमस्ते", language="hi")

    assert audio == b"audio-bytes"


def test_elevenlabs_tts_rejects_unsupported_language(settings, monkeypatch):
    settings.ELEVENLABS_TTS_VOICE_ID = "voice_123"
    monkeypatch.setattr("providers.elevenlabs.get_elevenlabs_client", lambda: FakeElevenLabsClient())

    with pytest.raises(ProviderError):
        ElevenLabsTextToSpeechProvider().synthesize(text="hello", language="as")


def test_elevenlabs_tts_requires_voice_id(settings):
    settings.ELEVENLABS_TTS_VOICE_ID = ""

    with pytest.raises(ProviderConfigurationError):
        ElevenLabsTextToSpeechProvider().synthesize(text="hello", language="en")


def test_infer_elevenlabs_audio_extension():
    assert infer_elevenlabs_audio_extension("mp3_44100_128") == "mp3"
    assert infer_elevenlabs_audio_extension("pcm_16000") == "pcm"


def test_elevenlabs_tts_retries_stream_conflict(monkeypatch, settings):
    settings.ELEVENLABS_TTS_VOICE_ID = "voice_123"
    settings.ELEVENLABS_TTS_MAX_RETRIES = 2
    settings.ELEVENLABS_TTS_RETRY_BASE_DELAY = 0
    client = FlakyElevenLabsClient()
    monkeypatch.setattr("providers.elevenlabs.get_elevenlabs_client", lambda: client)

    audio = ElevenLabsTextToSpeechProvider().synthesize(text="hello", language="en")

    assert audio == b"retry-ok"
    assert client.text_to_speech.calls == 2
