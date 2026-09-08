"""Tests for the scene target adapter."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.scene_state.scene_source import get_scene_targets

MOVIE_SCENE = {
    "name": "Movie",
    "entities": {
        "light.a": {"state": "on", "brightness": 100},
        "switch.b": "off",
    },
}


async def test_returns_targets_of_loaded_scene(hass: HomeAssistant) -> None:
    """The adapter returns one desired state per member."""
    assert await async_setup_component(hass, "scene", {"scene": [MOVIE_SCENE]})
    await hass.async_block_till_done()

    targets = get_scene_targets(hass, "scene.movie")

    assert targets is not None
    assert set(targets) == {"light.a", "switch.b"}
    assert targets["light.a"].state == "on"
    assert targets["light.a"].attributes["brightness"] == 100
    assert targets["switch.b"].state == "off"


async def test_returns_none_without_scene_platform(hass: HomeAssistant) -> None:
    """Without the scene platform there is nothing to read."""
    assert get_scene_targets(hass, "scene.movie") is None


async def test_returns_none_for_unknown_scene(hass: HomeAssistant) -> None:
    """A scene entity that is not loaded yields None."""
    assert await async_setup_component(hass, "scene", {"scene": [MOVIE_SCENE]})
    await hass.async_block_till_done()

    assert get_scene_targets(hass, "scene.other") is None


async def test_reload_is_reflected(hass: HomeAssistant) -> None:
    """After scene.reload the adapter returns the new members."""
    assert await async_setup_component(hass, "scene", {"scene": [MOVIE_SCENE]})
    await hass.async_block_till_done()

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={"scene": {"name": "Movie", "entities": {"light.c": "on"}}},
    ):
        await hass.services.async_call("scene", "reload", blocking=True)
        await hass.async_block_till_done()

    targets = get_scene_targets(hass, "scene.movie")

    assert targets is not None
    assert set(targets) == {"light.c"}
