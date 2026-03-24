import io
import wave

from providers.base import SpeechToTextProvider, SpeechToTextResult, TextToSpeechProvider, TranslationProvider


class MockSpeechToTextProvider(SpeechToTextProvider):
    def transcribe(self, *, file_path: str, language_hint: str | None = None) -> SpeechToTextResult:
        language = language_hint or "en"
        transcript = f"Mock transcript for {file_path.rsplit('/', 1)[-1]}"
        return SpeechToTextResult(transcript=transcript, source_language=language)


class MockTranslationProvider(TranslationProvider):
    def translate(self, *, text: str, source_language: str, target_language: str) -> str:
        return f"[{target_language}] {text}"


class MockTextToSpeechProvider(TextToSpeechProvider):
    def synthesize(self, *, text: str, language: str) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(8000)
            wav_file.writeframes(b"\x00\x00" * 8000)
        return buffer.getvalue()
