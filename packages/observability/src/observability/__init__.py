"""Local-first, privacy-preserving telemetry helpers."""

from observability.ollama_client import generate as instrumented_ollama_generate

__all__ = ["instrumented_ollama_generate"]
