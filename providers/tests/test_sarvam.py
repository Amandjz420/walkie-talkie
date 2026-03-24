import base64
from types import SimpleNamespace
from pathlib import Path

import pytest

from providers.base import ProviderError
from providers.sarvam import (
    SarvamSpeechToTextProvider,
    SarvamTextToSpeechProvider,
    SarvamTranslationProvider,
    _infer_audio_codec,
)


class FakeSpeechToTextAPI:
    def transcribe(self, *, file, model, mode, language_code=None, input_audio_codec=None):
        filename, _file_obj, content_type = file
        assert filename.endswith(".wav") or filename.endswith(".webm")
        assert content_type
        assert input_audio_codec in {"wav", "webm"}
        return SimpleNamespace(transcript="namaste", language_code="hi-IN")


class RetrySpeechToTextAPI:
    def __init__(self):
        self.calls = 0

    def transcribe(self, *, file, model, mode, language_code=None, input_audio_codec=None):
        self.calls += 1
        filename, _file_obj, _content_type = file
        if filename.endswith(".wav"):
            assert input_audio_codec == "wav"
            return SimpleNamespace(transcript="fallback worked", language_code="en-IN")
        raise Exception("Failed to read the file, please check the audio format.")


class FakeTextAPI:
    def translate(self, *, input, source_language_code, target_language_code, model):
        return SimpleNamespace(translated_text="hello")


class FakeTextToSpeechAPI:
    def convert(self, *, text, target_language_code, model, speaker, pace, output_audio_codec):
        return SimpleNamespace(audios=[base64.b64encode(b"audio-bytes").decode()])


class FakeSarvamClient:
    speech_to_text = FakeSpeechToTextAPI()
    text = FakeTextAPI()
    text_to_speech = FakeTextToSpeechAPI()


class FailingSpeechToTextAPI:
    def transcribe(self, **kwargs):
        raise Exception("Failed to read the file, please check the audio format.")


class FailingSarvamClient:
    speech_to_text = FailingSpeechToTextAPI()


class RetrySarvamClient:
    def __init__(self):
        self.speech_to_text = RetrySpeechToTextAPI()


@pytest.mark.django_db
def test_sarvam_stt_normalizes_detected_language(monkeypatch, tmp_path):
    monkeypatch.setattr("providers.sarvam.get_sarvam_client", lambda: FakeSarvamClient())
    sample_path = tmp_path / "sample.wav"
    sample_path.write_bytes(b"RIFFfake")

    result = SarvamSpeechToTextProvider().transcribe(file_path=str(sample_path), language_hint="hi")

    assert result.transcript == "namaste"
    assert result.source_language == "hi"


@pytest.mark.django_db
def test_sarvam_translation_and_tts_use_sdk_client(monkeypatch, settings):
    monkeypatch.setattr("providers.sarvam.get_sarvam_client", lambda: FakeSarvamClient())
    settings.SARVAM_TTS_SPEAKER = "shubh"
    settings.SARVAM_TTS_AUDIO_FORMAT = "wav"

    translated = SarvamTranslationProvider().translate(
        text="namaste",
        source_language="hi",
        target_language="en",
    )
    audio = SarvamTextToSpeechProvider().synthesize(text=translated, language="en")

    assert translated == "hello"
    assert audio == b"audio-bytes"


def test_infer_audio_codec_for_webm_path():
    assert _infer_audio_codec("/tmp/recording.webm") == "webm"
    assert _infer_audio_codec("/tmp/recording.wav") == "wav"
    assert _infer_audio_codec("/tmp/recording.unknown") is None


def test_sarvam_stt_raises_provider_error_with_api_message(monkeypatch, tmp_path):
    monkeypatch.setattr("providers.sarvam.get_sarvam_client", lambda: FailingSarvamClient())
    sample = tmp_path / "recording.wav"
    sample.write_bytes(b"fake")

    with pytest.raises(ProviderError) as exc:
        SarvamSpeechToTextProvider().transcribe(file_path=str(sample), language_hint=None)

    assert "Failed to read the file" in str(exc.value)


def test_sarvam_stt_retries_with_ffmpeg_normalized_wav(monkeypatch, tmp_path):
    retry_client = RetrySarvamClient()
    monkeypatch.setattr("providers.sarvam.get_sarvam_client", lambda: retry_client)

    def fake_transcode(input_path: str, output_path: str):
        Path(output_path).write_bytes(b"normalized")

    monkeypatch.setattr("providers.sarvam._transcode_audio_to_wav", fake_transcode)

    sample = tmp_path / "recording.ogg"
    sample.write_bytes(b"fake-ogg")

    result = SarvamSpeechToTextProvider().transcribe(file_path=str(sample), language_hint=None)

    assert result.transcript == "fallback worked"
    assert result.source_language == "en"
    assert retry_client.speech_to_text.calls == 2


def test_sarvam_stt_pre_normalizes_unsupported_browser_format(monkeypatch, tmp_path):
    retry_client = RetrySarvamClient()
    monkeypatch.setattr("providers.sarvam.get_sarvam_client", lambda: retry_client)

    def fake_transcode(input_path: str, output_path: str):
        Path(output_path).write_bytes(b"normalized")

    monkeypatch.setattr("providers.sarvam._transcode_audio_to_wav", fake_transcode)

    sample = tmp_path / "recording.webm"
    sample.write_bytes(b"fake-webm")

    result = SarvamSpeechToTextProvider().transcribe(file_path=str(sample), language_hint=None)

    assert result.transcript == "fallback worked"
    assert result.source_language == "en"
    assert retry_client.speech_to_text.calls == 1
