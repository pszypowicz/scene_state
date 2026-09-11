"""Tests for the attribute classification rules."""

from typing import Any

from homeassistant.core import State
import pytest

from custom_components.scene_state.attributes import (
    comparable,
    is_metadata,
    is_numeric,
    numeric_differences,
    select_color_attribute,
    selection_name,
)

SNAPSHOT_LIGHT = State(
    "light.a",
    "on",
    {
        "brightness": 100,
        "color_mode": "color_temp",
        "color_temp_kelvin": 2700,
        "hs_color": [30, 40],
        "rgb_color": [255, 180, 100],
        "xy_color": [0.4, 0.4],
        "min_color_temp_kelvin": 2200,
        "max_color_temp_kelvin": 6500,
        "effect_list": ["rainbow"],
        "effect": None,
        "supported_color_modes": ["color_temp"],
        "supported_features": 0,
        "friendly_name": "Bed light",
    },
)


@pytest.mark.parametrize(
    "attribute",
    [
        "assumed_state",
        "attribution",
        "device_class",
        "editable",
        "entity_id",
        "entity_picture",
        "friendly_name",
        "icon",
        "supported_features",
        "unit_of_measurement",
        "supported_color_modes",
        "available_modes",
        "min_color_temp_kelvin",
        "max_temp",
        "effect_list",
        "hvac_modes",
    ],
)
def test_is_metadata(attribute: str) -> None:
    """Capability attributes are recognized."""
    assert is_metadata(attribute) is True


@pytest.mark.parametrize(
    "attribute",
    ["brightness", "fan_mode", "temperature", "current_position", "volume_level"],
)
def test_is_not_metadata(attribute: str) -> None:
    """State attributes are not recognized as metadata."""
    assert is_metadata(attribute) is False


def test_comparable_keeps_state_attributes_only() -> None:
    """A snapshot light yields brightness and the selected representation."""
    assert comparable(SNAPSHOT_LIGHT) == ("brightness", "color_temp_kelvin")


def test_comparable_drops_none_values() -> None:
    """An attribute without a value takes no part in the comparison."""
    desired = State("light.a", "on", {"brightness": 100, "effect": None})
    assert comparable(desired) == ("brightness",)


def test_comparable_keeps_color_outside_light() -> None:
    """The color rule applies to lights only."""
    desired = State("foo.a", "on", {"hs_color": [30, 40], "xy_color": [0.4, 0.4]})
    assert set(comparable(desired)) == {"hs_color", "xy_color"}


def test_comparable_selects_by_order_without_color_mode() -> None:
    """Without color_mode the order of preference selects the representation."""
    desired = State("light.a", "on", {"hs_color": [30, 40], "xy_color": [0.4, 0.4]})
    assert comparable(desired) == ("hs_color",)


def test_select_color_attribute_white_mode_selects_nothing() -> None:
    """White mode carries no color representation."""
    assert select_color_attribute({"color_mode": "white"}) is None


@pytest.mark.parametrize(
    "attribute",
    [
        "color_temp_kelvin",
        "hs_color",
        "xy_color",
        "rgb_color",
        "rgbw_color",
        "rgbww_color",
    ],
)
def test_selection_name_folds_color(attribute: str) -> None:
    """Every color representation of a light is selected under one name."""
    assert selection_name(attribute, "light") == "color"


def test_selection_name_leaves_other_names() -> None:
    """Other attributes and other domains keep their name."""
    assert selection_name("brightness", "light") == "brightness"
    assert selection_name("hs_color", "foo") == "hs_color"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (100, True),
        (0.5, True),
        ([30, 40], True),
        ((30.0, 40.0), True),
        (True, False),
        ("rainbow", False),
        (["a", "b"], False),
        ([True, False], False),
        (None, False),
    ],
)
def test_is_numeric(value: Any, expected: bool) -> None:
    """A tolerance applies to a number or to a sequence of numbers."""
    assert is_numeric(value) is expected


def test_numeric_differences_number_and_sequence() -> None:
    """The difference is absolute, and the largest element wins for a sequence."""
    desired = State("light.a", "on", {"brightness": 100, "hs_color": [30, 40]})
    current = State("light.a", "on", {"brightness": 94, "hs_color": [32, 48]})
    assert numeric_differences(desired, current) == {
        "brightness": 6.0,
        "hs_color": 8.0,
    }


def test_numeric_differences_skips_unmeasurable() -> None:
    """A missing, non numeric, or mismatched value yields no difference."""
    desired = State(
        "light.a", "on", {"brightness": 100, "effect": "rainbow", "hs_color": [30, 40]}
    )
    current = State("light.a", "on", {"effect": "none", "hs_color": [30]})
    assert numeric_differences(desired, current) == {}
