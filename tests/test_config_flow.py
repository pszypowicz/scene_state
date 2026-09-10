"""Tests for the config flow."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
import voluptuous as vol

from custom_components.scene_state.const import (
    CONF_COMPARE,
    CONF_CONFIGURE,
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


MIXED_SCENE = {
    "name": "Mixed",
    "entities": {
        "light.a": {"state": "on", "brightness": 100, "effect": "none"},
        "cover.b": {"state": "open", "current_position": 70},
        "switch.c": "on",
    },
}
MIXED_OPTIONS = {
    CONF_ENTITY_ID: "scene.mixed",
    CONF_GRACE_PERIOD: 5.0,
    CONF_DEBOUNCE: 1.0,
}

COLOR_SCENE = {
    "name": "Color",
    "entities": {
        "light.a": {
            "state": "on",
            "brightness": 100,
            "color_mode": "hs",
            "hs_color": [30, 40],
        },
        "light.b": {"state": "on", "brightness": 200, "effect": "none"},
    },
}
COLOR_OPTIONS = {
    CONF_ENTITY_ID: "scene.color",
    CONF_GRACE_PERIOD: 5.0,
    CONF_DEBOUNCE: 1.0,
}


async def _open_color_options(
    hass: HomeAssistant,
    options: dict[str, Any] | None = None,
) -> tuple[MockConfigEntry, dict[str, Any]]:
    assert await async_setup_component(hass, "scene", {"scene": [COLOR_SCENE]})
    await hass.async_block_till_done()
    entry = MockConfigEntry(
        domain=DOMAIN, title="Color", options=options or COLOR_OPTIONS
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    return entry, result


async def _pick_light(hass: HomeAssistant, result: dict[str, Any]) -> dict[str, Any]:
    return await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_GRACE_PERIOD: 5.0, CONF_DEBOUNCE: 1.0, CONF_CONFIGURE: "light"},
    )


async def _setup_mixed_scene(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, "scene", {"scene": [MIXED_SCENE]})
    await hass.async_block_till_done()


def _marker(result: dict[str, Any], key: str) -> vol.Marker:
    for marker in result["data_schema"].schema:
        if marker.schema == key:
            return marker
    raise AssertionError(f"{key} is not in the schema")


def _keys(result: dict[str, Any]) -> list[str]:
    return [marker.schema for marker in result["data_schema"].schema]


def _selector_options(result: dict[str, Any], key: str) -> list[str]:
    schema = result["data_schema"].schema
    for marker, value in schema.items():
        if marker.schema == key:
            return [option["value"] for option in value.config["options"]]
    raise AssertionError(f"{key} is not in the schema")


def _suggested(result: dict[str, Any], key: str) -> Any:
    description = _marker(result, key).description or {}
    return description.get("suggested_value")


async def _open_options(hass: HomeAssistant) -> tuple[MockConfigEntry, dict[str, Any]]:
    entry = MockConfigEntry(domain=DOMAIN, title="Mixed", options=MIXED_OPTIONS)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    return entry, result


async def _remove_the_scene(hass: HomeAssistant) -> None:
    """Reload the scene platform with the tracked scene stripped of its members."""
    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={"scene": {"name": "Mixed", "entities": {}}},
    ):
        await hass.services.async_call("scene", "reload", blocking=True)
        await hass.async_block_till_done()


async def test_init_lists_scene_domains(hass: HomeAssistant) -> None:
    """The dropdown offers the domains that have something to compare."""
    await _setup_mixed_scene(hass)
    _entry, result = await _open_options(hass)

    assert result["step_id"] == "init"
    assert _selector_options(result, CONF_CONFIGURE) == ["cover", "light"]


async def test_init_without_scene_has_no_dropdown(hass: HomeAssistant) -> None:
    """An unloaded scene leaves the dropdown out."""
    entry = MockConfigEntry(domain=DOMAIN, title="Mixed", options=MIXED_OPTIONS)
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert CONF_CONFIGURE not in _keys(result)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_GRACE_PERIOD: 2.0, CONF_DEBOUNCE: 0.5}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_domain_step_suggests_every_name(hass: HomeAssistant) -> None:
    """A first visit arrives with every attribute selected."""
    await _setup_mixed_scene(hass)
    _entry, result = await _open_options(hass)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_GRACE_PERIOD: 5.0, CONF_DEBOUNCE: 1.0, CONF_CONFIGURE: "light"},
    )

    assert result["step_id"] == "domain"
    assert _selector_options(result, CONF_COMPARE) == ["brightness", "effect"]
    assert _suggested(result, CONF_COMPARE) == ["brightness", "effect"]


async def test_domain_step_stores_the_selection(hass: HomeAssistant) -> None:
    """The selection lands under the domain key, and configure does not."""
    await _setup_mixed_scene(hass)
    entry, result = await _open_options(hass)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_GRACE_PERIOD: 5.0, CONF_DEBOUNCE: 1.0, CONF_CONFIGURE: "light"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_COMPARE: ["effect"]}
    )
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_GRACE_PERIOD: 5.0, CONF_DEBOUNCE: 1.0}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["light"] == {CONF_COMPARE: ["effect"]}
    assert CONF_CONFIGURE not in entry.options


async def test_domain_step_stores_an_empty_selection(hass: HomeAssistant) -> None:
    """Comparing the state only is a legitimate choice."""
    await _setup_mixed_scene(hass)
    entry, result = await _open_options(hass)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_GRACE_PERIOD: 5.0, CONF_DEBOUNCE: 1.0, CONF_CONFIGURE: "cover"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_COMPARE: []}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_GRACE_PERIOD: 5.0, CONF_DEBOUNCE: 1.0}
    )
    await hass.async_block_till_done()

    assert entry.options["cover"] == {CONF_COMPARE: []}


async def test_domain_step_suggests_the_stored_selection(hass: HomeAssistant) -> None:
    """A second visit arrives with what the user stored."""
    await _setup_mixed_scene(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Mixed",
        options={**MIXED_OPTIONS, "light": {CONF_COMPARE: ["effect"]}},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_GRACE_PERIOD: 5.0, CONF_DEBOUNCE: 1.0, CONF_CONFIGURE: "light"},
    )

    assert _suggested(result, CONF_COMPARE) == ["effect"]


async def test_domain_step_skipped_keeps_the_stored_rule(hass: HomeAssistant) -> None:
    """A domain that lost every comparable attribute leaves its stored rule alone."""
    await _setup_mixed_scene(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Mixed",
        options={
            **MIXED_OPTIONS,
            "light": {CONF_COMPARE: ["brightness"], "brightness": 7},
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    await _remove_the_scene(hass)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_GRACE_PERIOD: 5.0, CONF_DEBOUNCE: 1.0, CONF_CONFIGURE: "light"},
    )
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_GRACE_PERIOD: 5.0, CONF_DEBOUNCE: 1.0}
    )
    await hass.async_block_till_done()

    assert entry.options["light"] == {CONF_COMPARE: ["brightness"], "brightness": 7}


async def test_init_closes_after_the_domain_step_is_skipped(
    hass: HomeAssistant,
) -> None:
    """A routing key left over from a skipped domain step does not strand the flow."""
    await _setup_mixed_scene(hass)
    entry, result = await _open_options(hass)
    await _remove_the_scene(hass)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_GRACE_PERIOD: 5.0, CONF_DEBOUNCE: 1.0, CONF_CONFIGURE: "light"},
    )
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_GRACE_PERIOD: 5.0, CONF_DEBOUNCE: 1.0}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_CONFIGURE not in entry.options


async def test_domain_step_ignores_a_malformed_stored_rule(hass: HomeAssistant) -> None:
    """A hand-edited, non-mapping domain value does not crash the domain step."""
    await _setup_mixed_scene(hass)
    entry = MockConfigEntry(
        domain=DOMAIN, title="Mixed", options={**MIXED_OPTIONS, "light": ["effect"]}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_GRACE_PERIOD: 5.0, CONF_DEBOUNCE: 1.0, CONF_CONFIGURE: "light"},
    )
    assert result["step_id"] == "domain"
    assert _suggested(result, CONF_COMPARE) == ["brightness", "effect"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_COMPARE: ["effect"]}
    )
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_GRACE_PERIOD: 5.0, CONF_DEBOUNCE: 1.0}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["light"] == {CONF_COMPARE: ["effect"]}


async def test_tolerances_offers_numeric_fields_only(hass: HomeAssistant) -> None:
    """A string attribute gets no tolerance field."""
    hass.states.async_set("light.a", "on", {"brightness": 100, "hs_color": [30, 40]})
    hass.states.async_set("light.b", "on", {"brightness": 200, "effect": "none"})
    _entry, result = await _open_color_options(hass)

    result = await _pick_light(hass, result)
    assert _selector_options(result, CONF_COMPARE) == [
        "brightness",
        "color",
        "effect",
    ]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_COMPARE: ["brightness", "effect"]}
    )

    assert result["step_id"] == "tolerances"
    assert _keys(result) == ["brightness"]


async def test_tolerances_covers_every_representation(hass: HomeAssistant) -> None:
    """A color selection renders a field per representation in use."""
    hass.states.async_set("light.a", "on", {"brightness": 100, "hs_color": [30, 40]})
    hass.states.async_set("light.b", "on", {"brightness": 200, "effect": "none"})
    _entry, result = await _open_color_options(hass)

    result = await _pick_light(hass, result)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_COMPARE: ["color"]}
    )

    assert _keys(result) == ["hs_color"]


async def test_tolerances_suggests_the_measured_difference(
    hass: HomeAssistant,
) -> None:
    """A first visit prefills the drift that the live states show."""
    hass.states.async_set("light.a", "on", {"brightness": 100, "hs_color": [30, 40]})
    hass.states.async_set("light.b", "on", {"brightness": 206, "effect": "none"})
    _entry, result = await _open_color_options(hass)

    result = await _pick_light(hass, result)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_COMPARE: ["brightness"]}
    )

    assert _suggested(result, "brightness") == 6.0
    assert "brightness 6" in result["description_placeholders"]["measured"]


async def test_tolerances_skips_unknown_members(hass: HomeAssistant) -> None:
    """An unavailable member contributes no measurement."""
    hass.states.async_set("light.a", "on", {"brightness": 100, "hs_color": [30, 40]})
    hass.states.async_set("light.b", "unavailable")
    _entry, result = await _open_color_options(hass)

    result = await _pick_light(hass, result)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_COMPARE: ["brightness"]}
    )

    assert _suggested(result, "brightness") == 0.0


async def test_tolerances_suggests_the_stored_value(hass: HomeAssistant) -> None:
    """A second visit keeps the number that the user chose."""
    hass.states.async_set("light.a", "on", {"brightness": 100, "hs_color": [30, 40]})
    hass.states.async_set("light.b", "on", {"brightness": 206, "effect": "none"})
    _entry, result = await _open_color_options(
        hass,
        options={
            **COLOR_OPTIONS,
            "light": {CONF_COMPARE: ["brightness"], "brightness": 2.0},
        },
    )

    result = await _pick_light(hass, result)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_COMPARE: ["brightness"]}
    )

    assert _suggested(result, "brightness") == 2.0
    assert "brightness 6" in result["description_placeholders"]["measured"]


async def test_tolerances_step_is_skipped_without_a_number(
    hass: HomeAssistant,
) -> None:
    """A selection of string attributes returns to the first step."""
    hass.states.async_set("light.a", "on", {"brightness": 100, "hs_color": [30, 40]})
    hass.states.async_set("light.b", "on", {"brightness": 200, "effect": "none"})
    _entry, result = await _open_color_options(hass)

    result = await _pick_light(hass, result)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_COMPARE: ["effect"]}
    )

    assert result["step_id"] == "init"


async def test_tolerances_are_stored_beside_the_selection(
    hass: HomeAssistant,
) -> None:
    """The submitted number lands under the domain key."""
    hass.states.async_set("light.a", "on", {"brightness": 100, "hs_color": [30, 40]})
    hass.states.async_set("light.b", "on", {"brightness": 206, "effect": "none"})
    entry, result = await _open_color_options(hass)

    result = await _pick_light(hass, result)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_COMPARE: ["brightness"]}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"brightness": 6.0}
    )
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_GRACE_PERIOD: 5.0, CONF_DEBOUNCE: 1.0}
    )
    await hass.async_block_till_done()

    assert entry.options["light"] == {
        CONF_COMPARE: ["brightness"],
        "brightness": 6.0,
    }


async def test_clearing_color_drops_its_tolerance(hass: HomeAssistant) -> None:
    """A cleared color box drops the tolerance of its representation."""
    hass.states.async_set("light.a", "on", {"brightness": 100, "hs_color": [30, 40]})
    hass.states.async_set("light.b", "on", {"brightness": 200, "effect": "none"})
    entry, result = await _open_color_options(
        hass,
        options={
            **COLOR_OPTIONS,
            "light": {CONF_COMPARE: ["color"], "hs_color": 5.0},
        },
    )

    result = await _pick_light(hass, result)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_COMPARE: ["effect"]}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_GRACE_PERIOD: 5.0, CONF_DEBOUNCE: 1.0}
    )
    await hass.async_block_till_done()

    assert entry.options["light"] == {CONF_COMPARE: ["effect"]}


async def test_tolerances_step_tolerates_a_missing_domain_rule(
    hass: HomeAssistant,
) -> None:
    """A domain picked after its scene loses its members reaches CREATE_ENTRY.

    The domain step skips itself once the scene has nothing left to compare,
    so the tolerances step runs with a domain that was never stored. Reading
    that domain rule must not raise.
    """
    await _setup_mixed_scene(hass)
    _entry, result = await _open_options(hass)
    await _remove_the_scene(hass)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_GRACE_PERIOD: 5.0, CONF_DEBOUNCE: 1.0, CONF_CONFIGURE: "light"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_GRACE_PERIOD: 5.0, CONF_DEBOUNCE: 1.0}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


def test_strings_and_translations_agree() -> None:
    """Home Assistant serves translations/en.json, so it must mirror strings.json."""
    root = Path(__file__).parent.parent / "custom_components" / "scene_state"
    strings = json.loads((root / "strings.json").read_text())
    english = json.loads((root / "translations" / "en.json").read_text())
    assert strings == english
