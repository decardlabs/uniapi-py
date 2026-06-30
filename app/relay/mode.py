from __future__ import annotations

from enum import IntEnum


class RelayMode(IntEnum):
    UNKNOWN = 0
    CHAT_COMPLETIONS = 1
    COMPLETIONS = 2
    EMBEDDINGS = 3
    MODERATIONS = 4
    IMAGES_GENERATIONS = 5
    IMAGES_EDITS = 6
    AUDIO_SPEECH = 7
    AUDIO_TRANSCRIPTION = 8
    AUDIO_TRANSLATION = 9
    RERANK = 10
    RESPONSE_API = 11
    CLAUDE_MESSAGES = 12
    REALTIME = 13
    VIDEOS = 14
    OCR = 15
    PROXY = 16


def relay_mode_from_path(path: str) -> RelayMode:
    if path.startswith("/v1/chat/completions"):
        return RelayMode.CHAT_COMPLETIONS
    if path.startswith("/v1/completions"):
        return RelayMode.COMPLETIONS
    if path.startswith("/v1/embeddings") or path.startswith("/v1/engines"):
        return RelayMode.EMBEDDINGS
    if path.startswith("/v1/moderations"):
        return RelayMode.MODERATIONS
    if path.startswith("/v1/images/generations"):
        return RelayMode.IMAGES_GENERATIONS
    if path.startswith("/v1/images/edits"):
        return RelayMode.IMAGES_EDITS
    if path.startswith("/v1/audio/speech"):
        return RelayMode.AUDIO_SPEECH
    if path.startswith("/v1/audio/transcriptions"):
        return RelayMode.AUDIO_TRANSCRIPTION
    if path.startswith("/v1/audio/translations"):
        return RelayMode.AUDIO_TRANSLATION
    if path.startswith("/v1/rerank") or path.startswith("/v2/rerank"):
        return RelayMode.RERANK
    if path.startswith("/v1/responses"):
        return RelayMode.RESPONSE_API
    if path.startswith("/v1/messages"):
        return RelayMode.CLAUDE_MESSAGES
    if path.startswith("/v1/realtime"):
        return RelayMode.REALTIME
    if path.startswith("/v1/videos"):
        return RelayMode.VIDEOS
    if path.startswith(("/api/paas/", "/v1/layout_parsing")):
        return RelayMode.OCR
    if path.startswith("/v1/oneapi/proxy"):
        return RelayMode.PROXY
    return RelayMode.UNKNOWN  # unknown path
