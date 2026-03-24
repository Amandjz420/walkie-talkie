from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SpeechToTextResult:
    transcript: str
    source_language: str


class ProviderError(Exception):
    pass


class ProviderConfigurationError(ProviderError):
    pass


class SpeechToTextProvider(ABC):
    @abstractmethod
    def transcribe(self, *, file_path: str, language_hint: str | None = None) -> SpeechToTextResult:
        raise NotImplementedError


class TranslationProvider(ABC):
    @abstractmethod
    def translate(self, *, text: str, source_language: str, target_language: str) -> str:
        raise NotImplementedError


class TextToSpeechProvider(ABC):
    @abstractmethod
    def synthesize(self, *, text: str, language: str) -> bytes:
        raise NotImplementedError
