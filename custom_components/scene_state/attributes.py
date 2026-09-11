"""Decide which attributes of a desired scene state take part in a comparison."""

from collections.abc import Mapping, Sequence
from typing import Any, Final

from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ATTRIBUTION,
    ATTR_DEVICE_CLASS,
    ATTR_EDITABLE,
    ATTR_ENTITY_ID,
    ATTR_ENTITY_PICTURE,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_SUPPORTED_FEATURES,
    ATTR_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import State

LIGHT_DOMAIN: Final = "light"
COLOR_NAME: Final = "color"

ATTR_COLOR_MODE: Final = "color_mode"
ATTR_COLOR_TEMP_KELVIN: Final = "color_temp_kelvin"

# The scene.create service stores the full live attribute set of a member, so a
# snapshot scene carries attributes that describe the entity rather than its
# state. Some are presentation, such as friendly_name and icon. Some are
# capability information, such as device_class and supported_features. The
# prefix and suffix rules below catch the capability lists, such as
# supported_color_modes and effect_list, that are not named here.
METADATA: Final = frozenset(
    {
        ATTR_ASSUMED_STATE,
        ATTR_ATTRIBUTION,
        ATTR_DEVICE_CLASS,
        ATTR_EDITABLE,
        ATTR_ENTITY_ID,
        ATTR_ENTITY_PICTURE,
        ATTR_FRIENDLY_NAME,
        ATTR_ICON,
        ATTR_SUPPORTED_FEATURES,
        ATTR_UNIT_OF_MEASUREMENT,
    }
)

# Home Assistant naming conventions, not the attributes of one platform.
METADATA_PREFIXES: Final = ("supported_", "available_", "min_", "max_")
METADATA_SUFFIXES: Final = ("_list", "_modes")

COLOR_MODE_ATTRIBUTES: Final[Mapping[str, str]] = {
    "color_temp": ATTR_COLOR_TEMP_KELVIN,
    "hs": "hs_color",
    "xy": "xy_color",
    "rgb": "rgb_color",
    "rgbw": "rgbw_color",
    "rgbww": "rgbww_color",
}

COLOR_ATTRIBUTE_ORDER: Final = (
    ATTR_COLOR_TEMP_KELVIN,
    "hs_color",
    "rgb_color",
    "xy_color",
    "rgbw_color",
    "rgbww_color",
)

COLOR_ATTRIBUTES: Final = frozenset(COLOR_ATTRIBUTE_ORDER)


def is_metadata(attribute: str) -> bool:
    """Return whether the attribute describes capability instead of state."""
    return (
        attribute in METADATA
        or attribute.startswith(METADATA_PREFIXES)
        or attribute.endswith(METADATA_SUFFIXES)
    )


def select_color_attribute(desired: Mapping[str, Any]) -> str | None:
    """Return the color attribute that carries the comparison, if any."""
    color_mode = desired.get(ATTR_COLOR_MODE)
    if color_mode is not None:
        return COLOR_MODE_ATTRIBUTES.get(str(color_mode))
    for attribute in COLOR_ATTRIBUTE_ORDER:
        if desired.get(attribute) is not None:
            return attribute
    return None


def _excluded_for_light(attributes: Mapping[str, Any]) -> frozenset[str]:
    """Return the light attributes that the color rule removes.

    A light reports every color representation at once, and all of them derive
    from one value, so one representation carries the comparison and the rest
    are excluded. `color_mode` is excluded too, because it only names which
    representation is authoritative and carries no color value of its own.
    """
    selected = select_color_attribute(attributes)
    return (COLOR_ATTRIBUTES - {selected}) | {ATTR_COLOR_MODE}


def comparable(desired: State) -> tuple[str, ...]:
    """Return the attribute names of the desired state that can be compared."""
    excluded = (
        _excluded_for_light(desired.attributes)
        if desired.domain == LIGHT_DOMAIN
        else frozenset[str]()
    )
    return tuple(
        attribute
        for attribute, value in desired.attributes.items()
        if value is not None
        and attribute not in excluded
        and not is_metadata(attribute)
    )


def selection_name(attribute: str, domain: str) -> str:
    """Return the name under which the user selects this attribute."""
    if domain == LIGHT_DOMAIN and attribute in COLOR_ATTRIBUTES:
        return COLOR_NAME
    return attribute


def _element(item: Any) -> float:
    """Convert one sequence element, rejecting a boolean the same way the scalar guard does."""
    if isinstance(item, bool):
        raise TypeError("bool is not numeric")
    return float(item)


def _numbers(value: Any) -> tuple[float, ...] | None:
    """Return the value as a tuple of floats, or None when it is not numeric."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return (float(value),)
    if isinstance(value, str) or not isinstance(value, Sequence):
        return None
    try:
        return tuple(_element(item) for item in value)
    except TypeError, ValueError:
        return None


def is_numeric(value: Any) -> bool:
    """Return whether a tolerance applies to the value."""
    return _numbers(value) is not None


def numeric_differences(desired: State, current: State) -> dict[str, float]:
    """Return the absolute difference per comparable numeric attribute."""
    differences: dict[str, float] = {}
    for attribute in comparable(desired):
        wanted = _numbers(desired.attributes.get(attribute))
        got = _numbers(current.attributes.get(attribute))
        if wanted is None or got is None or len(wanted) != len(got):
            continue
        differences[attribute] = max(
            abs(one - other) for one, other in zip(wanted, got, strict=True)
        )
    return differences
