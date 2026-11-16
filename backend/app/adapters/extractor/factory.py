from __future__ import annotations

from typing import Never

from app.adapters.extractor.base import ExtractorAdapter
from app.adapters.extractor.gateway_claude import GatewayClaudeExtractor
from app.adapters.extractor.mock import MockExtractor
from app.adapters.gateway.client import GatewayClient
from app.config import Settings


def get_extractor(settings: Settings) -> ExtractorAdapter:
    provider = settings.extractor_provider
    if provider == "mock":
        return MockExtractor()
    if provider == "gateway_claude":
        model = settings.extract_model.strip() or settings.claude_model.strip()
        return GatewayClaudeExtractor(GatewayClient.from_settings(settings), model)
    never: Never = provider
    raise AssertionError(never)
