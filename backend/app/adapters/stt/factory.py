from __future__ import annotations

from typing import Never

from app.adapters.gateway.client import GatewayClient
from app.adapters.stt.base import STTAdapter
from app.adapters.stt.gateway import GatewaySTT
from app.adapters.stt.mock import MockSTT
from app.config import Settings


def get_stt_adapter(settings: Settings) -> STTAdapter:
    provider = settings.stt_provider
    if provider == "mock":
        return MockSTT()
    if provider == "gateway":
        client = GatewayClient(
            settings.gateway_base_url,
            settings.gateway_api_key,
            timeout_seconds=settings.gateway_timeout_seconds,
            max_retries=settings.gateway_max_retries,
            retry_backoff_seconds=settings.gateway_retry_backoff_seconds,
        )
        return GatewaySTT(
            client,
            model=settings.stt_model,
            language=settings.stt_language,
            diarization=settings.stt_diarization,
            poll_interval_seconds=settings.stt_poll_interval_seconds,
            poll_timeout_seconds=settings.stt_poll_timeout_seconds,
            max_audio_bytes=settings.stt_max_audio_bytes,
            ffmpeg_bin=settings.ffmpeg_bin,
        )
    never: Never = provider
    raise AssertionError(never)
