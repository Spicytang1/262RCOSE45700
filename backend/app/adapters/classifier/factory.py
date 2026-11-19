from __future__ import annotations

from typing import Never

from app.adapters.classifier.base import ClassifierAdapter
from app.adapters.classifier.gateway_jev import GatewayJevClassifier
from app.adapters.classifier.mock import MockClassifier
from app.adapters.gateway.client import GatewayClient
from app.config import Settings


def get_classifier(settings: Settings) -> ClassifierAdapter:
    provider = settings.classifier_provider
    if provider == "mock":
        return MockClassifier()
    if provider == "gateway_jev":
        return GatewayJevClassifier(GatewayClient.from_settings(settings), settings.jev_model_version)
    never: Never = provider
    raise AssertionError(never)
