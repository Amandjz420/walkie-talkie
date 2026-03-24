from pathlib import Path
from types import SimpleNamespace

import pytest

from providers.base import ProviderError
from providers.groq import GroqSpeechToTextProvider, GroqTranslationProvider


class FakeGroqAudioAPI:
    def transcriptions(self):
        raise NotImplementedError


class FakeTranscriptionsAPI:
    def create(self, *, file, model, temperature, response_format, language=None, prompt=None):
        filename, payload, content_type = file
        assert filename.endswith(".wav") or filename.endswith(".webm")
        assert payload
        assert content_type
        assert model == "whisper-large-v3-turbo"
        assert response_format == "verbose_json"
        assert temperature == 0.0
        return SimpleNamespace(text="namaste", language="hi")


class ConstrainedLanguageTranscriptionsAPI:
    def __init__(self):
        self.calls = []

    def create(self, *, file, model, temperature, response_format, language=None, prompt=None):
        self.calls.append(language)
        if language is None:
            return SimpleNamespace(text="Que ser bom.", language="portuguese")
        if language == "en":
            assert prompt
            return SimpleNamespace(text="How good it is", language="english")
        if language == "hi":
            assert prompt
            return SimpleNamespace(text="यह अच्छा है", language="hindi")
        raise AssertionError(f"unexpected language hint: {language}")


class FakeChatCompletionsAPI:
    def create(self, *, model, temperature, messages):
        assert model == "llama-3.3-70b-versatile"
        assert temperature == 0
        assert messages[1]["content"] == "namaste"
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="hello")
                )
            ]
        )


class FakeGroqClient:
    def __init__(self):
        self.audio = SimpleNamespace(transcriptions=FakeTranscriptionsAPI())
        self.chat = SimpleNamespace(completions=FakeChatCompletionsAPI())


class FailingTranscriptionsAPI:
    def create(self, **kwargs):
        raise Exception("unsupported audio format")


class RetryTranscriptionsAPI:
    def __init__(self):
        self.calls = 0
        self.filenames = []

    def create(self, *, file, **kwargs):
        self.calls += 1
        filename, payload, _content_type = file
        self.filenames.append(filename)
        if filename.endswith(".wav"):
            return SimpleNamespace(text="retry worked", language="en")
        raise Exception("invalid audio format")


class RetryGroqClient:
    def __init__(self):
        self.audio = SimpleNamespace(transcriptions=RetryTranscriptionsAPI())
        self.chat = SimpleNamespace(completions=FakeChatCompletionsAPI())


class ConstrainedLanguageGroqClient:
    def __init__(self):
        self.audio = SimpleNamespace(transcriptions=ConstrainedLanguageTranscriptionsAPI())
        self.chat = SimpleNamespace(completions=FakeChatCompletionsAPI())


class ManualHintTranscriptionsAPI:
    def __init__(self):
        self.calls = []

    def create(self, *, file, model, temperature, response_format, language=None, prompt=None):
        self.calls.append(language)
        assert prompt
        return SimpleNamespace(text="सब मज़े में", language="portuguese")


class ManualHintGroqClient:
    def __init__(self):
        self.audio = SimpleNamespace(transcriptions=ManualHintTranscriptionsAPI())
        self.chat = SimpleNamespace(completions=FakeChatCompletionsAPI())


@pytest.mark.django_db
def test_groq_stt_transcribes_audio(monkeypatch, settings, tmp_path):
    settings.GROQ_STT_MODEL = "whisper-large-v3-turbo"
    settings.GROQ_STT_HINTED_MODEL = "whisper-large-v3-turbo"
    monkeypatch.setattr("providers.groq.get_groq_client", lambda: FakeGroqClient())
    sample = tmp_path / "sample.wav"
    sample.write_bytes(b"RIFFfake")

    result = GroqSpeechToTextProvider().transcribe(file_path=str(sample), language_hint="hi")

    assert result.transcript == "namaste"
    assert result.source_language == "hi"


@pytest.mark.django_db
def test_groq_translation_uses_chat_completion(monkeypatch, settings):
    settings.GROQ_TRANSLATION_MODEL = "llama-3.3-70b-versatile"
    monkeypatch.setattr("providers.groq.get_groq_client", lambda: FakeGroqClient())

    translated = GroqTranslationProvider().translate(
        text="namaste",
        source_language="hi",
        target_language="en",
    )

    assert translated == "hello"


def test_groq_stt_retries_with_ffmpeg_normalized_wav(monkeypatch, tmp_path, settings):
    settings.GROQ_STT_MODEL = "whisper-large-v3-turbo"
    retry_client = RetryGroqClient()
    monkeypatch.setattr("providers.groq.get_groq_client", lambda: retry_client)

    def fake_transcode(input_path: str, output_path: str):
        Path(output_path).write_bytes(b"normalized")

    monkeypatch.setattr("providers.groq._transcode_audio_to_wav", fake_transcode)

    sample = tmp_path / "recording.ogg"
    sample.write_bytes(b"fake-ogg")

    result = GroqSpeechToTextProvider().transcribe(file_path=str(sample), language_hint=None)

    assert result.transcript == "retry worked"
    assert result.source_language == "en"
    assert retry_client.audio.transcriptions.calls == 2


def test_groq_stt_pre_normalizes_unsupported_browser_format(monkeypatch, tmp_path, settings):
    settings.GROQ_STT_MODEL = "whisper-large-v3-turbo"
    retry_client = RetryGroqClient()
    monkeypatch.setattr("providers.groq.get_groq_client", lambda: retry_client)

    def fake_transcode(input_path: str, output_path: str):
        Path(output_path).write_bytes(b"normalized")

    monkeypatch.setattr("providers.groq._transcode_audio_to_wav", fake_transcode)

    sample = tmp_path / "recording.opus"
    sample.write_bytes(b"fake-opus")

    result = GroqSpeechToTextProvider().transcribe(file_path=str(sample), language_hint=None)

    assert result.transcript == "retry worked"
    assert result.source_language == "en"
    assert retry_client.audio.transcriptions.calls == 1


def test_groq_stt_pre_normalizes_webm_browser_format(monkeypatch, tmp_path, settings):
    settings.GROQ_STT_MODEL = "whisper-large-v3-turbo"
    retry_client = RetryGroqClient()
    monkeypatch.setattr("providers.groq.get_groq_client", lambda: retry_client)

    def fake_transcode(input_path: str, output_path: str):
        Path(output_path).write_bytes(b"normalized")

    monkeypatch.setattr("providers.groq._transcode_audio_to_wav", fake_transcode)

    sample = tmp_path / "recording.webm"
    sample.write_bytes(b"fake-webm")

    result = GroqSpeechToTextProvider().transcribe(file_path=str(sample), language_hint=None)

    assert result.transcript == "retry worked"
    assert result.source_language == "en"
    assert retry_client.audio.transcriptions.calls == 1
    assert retry_client.audio.transcriptions.filenames == ["recording.wav"]


def test_groq_translation_raises_provider_error(monkeypatch):
    class FailingChatCompletionsAPI:
        def create(self, **kwargs):
            raise Exception("translation exploded")

    class FailingGroqClient:
        def __init__(self):
            self.audio = SimpleNamespace(transcriptions=FakeTranscriptionsAPI())
            self.chat = SimpleNamespace(completions=FailingChatCompletionsAPI())

    monkeypatch.setattr("providers.groq.get_groq_client", lambda: FailingGroqClient())

    with pytest.raises(ProviderError):
        GroqTranslationProvider().translate(text="hi", source_language="en", target_language="fr")


def test_groq_stt_constrains_auto_detection_to_allowed_languages(monkeypatch, settings, tmp_path):
    settings.GROQ_STT_MODEL = "whisper-large-v3-turbo"
    settings.GROQ_STT_HINTED_MODEL = "whisper-large-v3"
    settings.GROQ_STT_ALLOWED_AUTO_LANGUAGES = "en,hi"
    client = ConstrainedLanguageGroqClient()
    monkeypatch.setattr("providers.groq.get_groq_client", lambda: client)
    sample = tmp_path / "sample.wav"
    sample.write_bytes(b"RIFFfake")

    result = GroqSpeechToTextProvider().transcribe(file_path=str(sample), language_hint=None)

    assert result.transcript == "यह अच्छा है"
    assert result.source_language == "hi"
    assert client.audio.transcriptions.calls[0] is None
    assert set(client.audio.transcriptions.calls[1:]) == {"en", "hi"}


def test_groq_stt_manual_language_hint_disables_auto_detection(monkeypatch, settings, tmp_path):
    settings.GROQ_STT_MODEL = "whisper-large-v3-turbo"
    settings.GROQ_STT_HINTED_MODEL = "whisper-large-v3"
    client = ManualHintGroqClient()
    monkeypatch.setattr("providers.groq.get_groq_client", lambda: client)
    sample = tmp_path / "sample.wav"
    sample.write_bytes(b"RIFFfake")

    result = GroqSpeechToTextProvider().transcribe(file_path=str(sample), language_hint="hi")

    assert result.transcript == "सब मज़े में"
    assert result.source_language == "hi"
    assert client.audio.transcriptions.calls == ["hi"]
