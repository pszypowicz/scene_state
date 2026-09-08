"""Tests for the config flow."""

from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.scene_state.const import (
    CONF_DEBOUNCE,
    CONF_GRACE_PERIOD,
    DOMAIN,
)

MOVIE_SCENE = {"name": "Movie", "entities": {"light.a": "on"}}
MOVIE_OPTIONS = {
    CONF_ENTITY_ID: "scene.movie",
    CONF_GRACE_PERIOD: 5.0,
    CONF_DEBOUNCE: 1.0,
}


async def _setup_scene(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, "scene", {"scene": [MOVIE_SCENE]})
    await hass.async_block_till_done()


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """The user step creates an entry titled after the scene."""
    await _setup_scene(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "custom_components.scene_state.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOVIE_OPTIONS
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Movie"
    assert result["options"] == MOVIE_OPTIONS
    assert mock_setup_entry.call_count == 1


async def test_duplicate_scene_aborts(hass: HomeAssistant) -> None:
    """A second entry for the same scene is refused."""
    await _setup_scene(hass)
    MockConfigEntry(domain=DOMAIN, title="Movie", options=MOVIE_OPTIONS).add_to_hass(
        hass
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOVIE_OPTIONS
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_updates_and_reloads(hass: HomeAssistant) -> None:
    """The options step stores new timings and reloads the entry."""
    await _setup_scene(hass)
    entry = MockConfigEntry(domain=DOMAIN, title="Movie", options=MOVIE_OPTIONS)
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.scene_state.async_setup_entry", return_value=True
        ) as mock_setup_entry,
        patch(
            "custom_components.scene_state.async_unload_entry", return_value=True
        ) as mock_unload_entry,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert mock_setup_entry.call_count == 1

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_GRACE_PERIOD: 2.0, CONF_DEBOUNCE: 0.0}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        CONF_ENTITY_ID: "scene.movie",
        CONF_GRACE_PERIOD: 2.0,
        CONF_DEBOUNCE: 0.0,
    }
    assert mock_unload_entry.call_count == 1
    assert mock_setup_entry.call_count == 2
    assert entry.state is ConfigEntryState.LOADED
