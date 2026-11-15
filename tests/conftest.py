from __future__ import annotations

import pytest

from harness.config import HarnessConfig


@pytest.fixture
def config_factory():
    def factory(**overrides) -> HarnessConfig:
        defaults = {
            "app_name": "Acme Shop",
            "description": "An online storefront for test fixtures.",
        }
        defaults.update(overrides)
        return HarnessConfig(**defaults)

    return factory
