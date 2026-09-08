"""Shared fixtures for the Scene State tests."""

import pytest


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow the loader to find the integration under custom_components."""
