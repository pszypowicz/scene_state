"""Tests for the binary sensor."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import (
    CONF_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed_exact,
    async_mock_service,
)

from custom_components.scene_state.const import (
    CONF_DEBOUNCE,
    CONF_GRACE_PERIOD,
    DOMAIN,
)

SENSOR_ENTITY_ID = "binary_sensor.scene_state_movie"
MOVIE_SCENE = {
    "id": "movie",
    "name": "Movie",
    "entities": {
        "light.a": {"state": "on", "brightness": 100},
        "switch.b": "off",
    },
}


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


def _set_members_matching(hass: HomeAssistant) -> None:
    hass.states.async_set("light.a", "on", {"brightness": 100})
    hass.states.async_set("switch.b", "off")


async def _advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float
) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed_exact(hass)
    await hass.async_block_till_done()


async def test_sensor_is_on_when_members_match(hass: HomeAssistant) -> None:
    """All members match, the sensor is on with empty mismatch list."""
    _set_members_matching(hass)
    await _setup(hass)

    state = hass.states.get(SENSOR_ENTITY_ID)

    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["scene_entity_id"] == "scene.movie"
    assert state.attributes["mismatched_entities"] == []
    assert state.attributes["friendly_name"] == "Scene state Movie"


async def test_sensor_turns_off_after_debounce(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A member change flips the sensor after the debounce."""
    _set_members_matching(hass)
    await _setup(hass)

    hass.states.async_set("light.a", "on", {"brightness": 10})
    await _advance(hass, freezer, 1.5)

    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["mismatched_entities"] == ["light.a"]


async def test_sensor_is_unknown_with_unavailable_member(hass: HomeAssistant) -> None:
    """An unavailable member yields unknown."""
    hass.states.async_set("light.a", "on", {"brightness": 100})
    hass.states.async_set("switch.b", STATE_UNAVAILABLE)
    await _setup(hass)

    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_sensor_unavailable_when_scene_missing(hass: HomeAssistant) -> None:
    """A reload that drops the scene makes the sensor unavailable."""
    _set_members_matching(hass)
    await _setup(hass)

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={"scene": {"name": "Other", "entities": {"light.a": "on"}}},
    ):
        await hass.services.async_call("scene", "reload", blocking=True)
        await hass.async_block_till_done()

    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_activation_waits_for_grace_period(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Activating the scene evaluates once the grace period ends."""
    async_mock_service(hass, "light", "turn_on")
    async_mock_service(hass, "switch", "turn_off")
    hass.states.async_set("light.a", "on", {"brightness": 10})
    hass.states.async_set("switch.b", "off")
    await _setup(hass)
    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    await hass.services.async_call(
        "scene", "turn_on", {"entity_id": "scene.movie"}, blocking=True
    )
    hass.states.async_set("light.a", "on", {"brightness": 100})
    await _advance(hass, freezer, 2.0)
    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    await _advance(hass, freezer, 3.5)

    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


async def test_unload_makes_sensor_unavailable(hass: HomeAssistant) -> None:
    """Unloading the entry marks the entity unavailable."""
    _set_members_matching(hass)
    entry = await _setup(hass)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_unload_with_pending_debounce_stops_tracker(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Unloading while a debounce runs leaves no timer and no later update."""
    _set_members_matching(hass)
    entry = await _setup(hass)
    hass.states.async_set("light.a", "on", {"brightness": 10})
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    await _advance(hass, freezer, 2.0)

    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_stored_tolerance_turns_the_sensor_on(hass: HomeAssistant) -> None:
    """A tolerance in the entry options reaches the comparison."""
    assert await async_setup_component(hass, "scene", {"scene": [MOVIE_SCENE]})
    await hass.async_block_till_done()
    hass.states.async_set("light.a", "on", {"brightness": 103})
    hass.states.async_set("switch.b", "off")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Movie",
        options={
            CONF_ENTITY_ID: "scene.movie",
            CONF_GRACE_PERIOD: 0.0,
            CONF_DEBOUNCE: 0.0,
            "light": {"compare": ["brightness"], "brightness": 3},
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
