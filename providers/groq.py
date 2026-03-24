from functools import lru_cache
import mimetypes
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from django.conf import settings

from providers.base import (
    ProviderConfigurationError,
    ProviderError,
    SpeechToTextProvider,
    SpeechToTextResult,
    TranslationProvider,
)

GROQ_STT_PASSTHROUGH_EXTENSIONS = {
    ".flac",
    ".m4a",
    ".mp3",
    ".mpga",
    ".mpeg",
    ".ogg",
    ".wav",
}

LANGUAGE_NAME_TO_CODE = {
    "english": "en",
    "en": "en",
    "hindi": "hi",
    "hi": "hi",
    "portuguese": "pt",
    "pt": "pt",
}

ENGLISH_HINT_WORDS = {"and", "go", "hello", "movie", "plans", "start", "thank", "the", "will", "with", "you"}


def _load_groq_client_class():
    try:
        from groq import Groq
    except ImportError as exc:
        raise ProviderConfigurationError(
            "Groq provider selected but the 'groq' package is not installed."
        ) from exc
    return Groq


def _extract_groq_error_message(exc: Exception) -> str:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
        if body.get("message"):
            return str(body["message"])
    message = getattr(exc, "message", None)
    if message:
        return str(message)
    return str(exc).strip() or "Groq request failed."


def _raise_provider_error(exc: Exception, *, action: str) -> None:
    raise ProviderError(f"Groq {action} failed: {_extract_groq_error_message(exc)}") from exc


def _to_app_language(code: str | None) -> str:
    if not code:
        return "unknown"
    normalized = code.strip().split("-")[0].lower()
    return LANGUAGE_NAME_TO_CODE.get(normalized, normalized)


def _infer_content_type(file_path: str) -> str:
    guessed_type, _ = mimetypes.guess_type(file_path)
    return guessed_type or "application/octet-stream"


def _should_pre_normalize_for_stt(file_path: str) -> bool:
    return Path(file_path).suffix.lower() not in GROQ_STT_PASSTHROUGH_EXTENSIONS


def _should_retry_stt_with_transcode(exc: Exception) -> bool:
    message = _extract_groq_error_message(exc).lower()
    return "audio" in message or "file" in message or "decode" in message or "format" in message


def _transcode_audio_to_wav(input_path: str, output_path: str) -> None:
    ffmpeg_binary = getattr(settings, "FFMPEG_BINARY", "ffmpeg")
    resolved_binary = shutil.which(ffmpeg_binary) or ffmpeg_binary
    try:
        subprocess.run(
            [
                resolved_binary,
                "-y",
                "-i",
                input_path,
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                output_path,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise ProviderError("Audio normalization via ffmpeg failed before speech-to-text.") from exc


@lru_cache(maxsize=1)
def get_groq_client():
    api_key = settings.GROQ_API_KEY
    if not api_key:
        raise ProviderConfigurationError("GROQ_API_KEY must be set when using Groq providers.")
    Groq = _load_groq_client_class()
    return Groq(api_key=api_key)


def _allowed_auto_languages() -> list[str]:
    configured = getattr(settings, "GROQ_STT_ALLOWED_AUTO_LANGUAGES", "")
    return [language.strip().lower() for language in configured.split(",") if language.strip()]


def _contains_devanagari(text: str) -> bool:
    return any("\u0900" <= char <= "\u097f" for char in text)


def _english_word_hits(text: str) -> int:
    words = {word.lower() for word in re.findall(r"[A-Za-z']+", text)}
    return len(words & ENGLISH_HINT_WORDS)


def _score_transcription_candidate(result: SpeechToTextResult, *, allowed_languages: set[str]) -> float:
    transcript = (result.transcript or "").strip()
    score = 0.0
    if result.source_language in allowed_languages:
        score += 4
    score += min(len(transcript) / 24, 3)
    if _contains_devanagari(transcript):
        score += 5 if result.source_language == "hi" else -2
    english_hits = _english_word_hits(transcript)
    if english_hits:
        score += 1.5 + min(english_hits, 3)
        if result.source_language == "en":
            score += 2
    if result.source_language not in allowed_languages:
        score -= 3
    return score


def _stt_prompt_for_language(language_hint: str | None) -> str | None:
    if language_hint == "hi":
        configured = getattr(settings, "GROQ_STT_PROMPT_HI", "").strip()
        if configured:
            return configured
        return (
            "The audio is Hindi or Hinglish. Prefer natural everyday spoken Hindi and common Hinglish usage. "
            "It is okay to keep common English words like dinner, date, movie, plan, special, suit, and home in English "
            "when that sounds natural. Use Devanagari for Hindi words, but do not force pure Devanagari if the speaker "
            "is clearly code-mixing. Prefer realistic conversational wording over phonetically similar nonsense words."
        )
    if language_hint == "en":
        configured = getattr(settings, "GROQ_STT_PROMPT_EN", "").strip()
        if configured:
            return configured
        return (
            "The audio is English. Return a clean English transcript with standard punctuation."
        )
    return None


class GroqSpeechToTextProvider(SpeechToTextProvider):
    def transcribe(self, *, file_path: str, language_hint: str | None = None) -> SpeechToTextResult:
        if language_hint:
            normalized_hint = _to_app_language(language_hint)
            result = self._transcribe_with_optional_normalization(
                file_path=file_path,
                language_hint=normalized_hint,
            )
            return SpeechToTextResult(
                transcript=result.transcript,
                source_language=normalized_hint,
            )

        initial_result = self._transcribe_with_optional_normalization(file_path=file_path, language_hint=None)
        allowed_languages = set(_allowed_auto_languages())
        if not allowed_languages or initial_result.source_language in allowed_languages:
            return initial_result

        candidates = [initial_result]
        for allowed_language in allowed_languages:
            candidates.append(
                self._transcribe_with_optional_normalization(
                    file_path=file_path,
                    language_hint=allowed_language,
                )
            )
        return max(
            candidates,
            key=lambda result: _score_transcription_candidate(result, allowed_languages=allowed_languages),
        )

    def _transcribe_with_optional_normalization(
        self,
        *,
        file_path: str,
        language_hint: str | None,
    ) -> SpeechToTextResult:
        client = get_groq_client()
        request_kwargs = self._build_request_kwargs(language_hint=language_hint)

        if _should_pre_normalize_for_stt(file_path):
            with tempfile.TemporaryDirectory() as temp_dir:
                normalized_path = str(Path(temp_dir) / f"{Path(file_path).stem}.wav")
                _transcode_audio_to_wav(file_path, normalized_path)
                try:
                    return self._transcribe_file(client=client, file_path=normalized_path, request_kwargs=request_kwargs)
                except Exception as exc:
                    _raise_provider_error(exc, action="speech-to-text")

        try:
            return self._transcribe_file(client=client, file_path=file_path, request_kwargs=request_kwargs)
        except Exception as exc:
            if not _should_retry_stt_with_transcode(exc):
                _raise_provider_error(exc, action="speech-to-text")
            with tempfile.TemporaryDirectory() as temp_dir:
                normalized_path = str(Path(temp_dir) / f"{Path(file_path).stem}.wav")
                try:
                    _transcode_audio_to_wav(file_path, normalized_path)
                except ProviderError:
                    _raise_provider_error(exc, action="speech-to-text")
                try:
                    return self._transcribe_file(client=client, file_path=normalized_path, request_kwargs=request_kwargs)
                except Exception as retry_exc:
                    _raise_provider_error(retry_exc, action="speech-to-text")

    @staticmethod
    def _build_request_kwargs(*, language_hint: str | None) -> dict:
        request_kwargs = {
            "model": settings.GROQ_STT_HINTED_MODEL if language_hint else settings.GROQ_STT_MODEL,
            "temperature": 0.0,
            "response_format": "verbose_json",
        }
        if language_hint:
            request_kwargs["language"] = language_hint.split("-")[0].lower()
            prompt = _stt_prompt_for_language(request_kwargs["language"])
            if prompt:
                request_kwargs["prompt"] = prompt
        return request_kwargs

    @staticmethod
    def _transcribe_file(*, client, file_path: str, request_kwargs: dict) -> SpeechToTextResult:
        with open(file_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                file=(Path(file_path).name, audio_file.read(), _infer_content_type(file_path)),
                **request_kwargs,
            )
        transcript = getattr(response, "text", None) or response.get("text", "")
        language = getattr(response, "language", None)
        if language is None and isinstance(response, dict):
            language = response.get("language")
        return SpeechToTextResult(
            transcript=transcript,
            source_language=_to_app_language(language),
        )


class GroqTranslationProvider(TranslationProvider):
    def translate(self, *, text: str, source_language: str, target_language: str) -> str:
        client = get_groq_client()
        prompt = (
            "You are a translation engine. Translate the user's text from "
            f"{source_language} to {target_language}. "
            "Return only the translated text with no explanation, quotes, labels, or extra formatting."
        )
        try:
            response = client.chat.completions.create(
                model=settings.GROQ_TRANSLATION_MODEL,
                temperature=0,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text},
                ],
            )
        except Exception as exc:
            _raise_provider_error(exc, action="translation")
        content = response.choices[0].message.content if response.choices else ""
        return (content or "").strip()
