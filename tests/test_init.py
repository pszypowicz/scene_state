"""Tests for the integration setup."""

from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from custom_components.scene_state.const import DOMAIN


async def test_integration_is_discoverable(hass: HomeAssistant) -> None:
    """The loader finds the custom integration and reads its manifest."""
    integration = await async_get_integration(hass, DOMAIN)

    assert integration.domain == DOMAIN
    assert str(integration.version) == "0.0.1"
    assert integration.integration_type == "helper"
