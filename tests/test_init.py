"""Tests for the integration setup."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.scene_state.const import (
    CONF_DEBOUNCE,
    CONF_GRACE_PERIOD,
    DOMAIN,
)

MOVIE_SCENE = {"id": "movie", "name": "Movie", "entities": {"light.a": "on"}}


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    assert await async_setup_component(hass, "scene", {"scene": [MOVIE_SCENE]})
    await hass.async_block_till_done()
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Movie",
        options={
            CONF_ENTITY_ID: "scene.movie",
            CONF_GRACE_PERIOD: 5.0,
            CONF_DEBOUNCE: 1.0,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_integration_is_discoverable(hass: HomeAssistant) -> None:
    """The loader finds the custom integration and reads its manifest."""
    integration = await async_get_integration(hass, DOMAIN)

    assert integration.domain == DOMAIN
    assert integration.version is not None
    assert integration.integration_type == "helper"


async def test_setup_and_unload(hass: HomeAssistant) -> None:
    """The entry loads and unloads."""
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED

    registry = er.async_get(hass)
    sensor_entry = registry.async_get("binary_sensor.scene_state_movie")
    assert sensor_entry is not None
    assert sensor_entry.unique_id == entry.entry_id

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_scene_rename_updates_option(hass: HomeAssistant) -> None:
    """A new entity ID for the scene lands in the entry options."""
    entry = await _setup(hass)
    registry = er.async_get(hass)

    registry.async_update_entity("scene.movie", new_entity_id="scene.film")
    await hass.async_block_till_done()

    assert entry.options[CONF_ENTITY_ID] == "scene.film"
    state = hass.states.get("binary_sensor.scene_state_movie")
    assert state is not None
    assert state.attributes["scene_entity_id"] == "scene.film"


async def test_scene_removal_removes_entry(hass: HomeAssistant) -> None:
    """Removing the scene from the registry removes the entry."""
    entry = await _setup(hass)
    registry = er.async_get(hass)

    registry.async_remove("scene.movie")
    await hass.async_block_till_done()

    assert hass.config_entries.async_get_entry(entry.entry_id) is None
