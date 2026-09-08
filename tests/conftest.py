"""Shared fixtures for the Scene State tests."""

from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations: None) -> Iterator[None]:
    """Allow the loader to find the integration under custom_components."""
    yield  # noqa: PT022 - generator fixture kept open for teardown code added by later tasks
