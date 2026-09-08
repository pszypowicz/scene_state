"""Compare a desired scene state with the current state of an entity."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from homeassistant.core import State

type Comparator = Callable[[Any, Any], bool]

STATES_WITHOUT_ATTRIBUTES: frozenset[str] = frozenset({"off", "closed"})
FLOAT_MARGIN = 1e-9

ATTR_COLOR_MODE = "color_mode"
ATTR_COLOR_TEMP_KELVIN = "color_temp_kelvin"
ATTR_MIN_COLOR_TEMP_KELVIN = "min_color_temp_kelvin"
ATTR_MAX_COLOR_TEMP_KELVIN = "max_color_temp_kelvin"


@dataclass(frozen=True, slots=True)
class MatchResult:
    """Outcome of one comparison."""

    matches: bool
    reason: str | None = None


def _exact(wanted: Any, got: Any) -> bool:
    return bool(wanted == got)


def _within(tolerance: float) -> Comparator:
    def compare(wanted: Any, got: Any) -> bool:
        try:
            difference = abs(float(wanted) - float(got))
        except TypeError, ValueError:
            return False
        # Float subtraction can exceed the tolerance by a rounding error.
        return difference <= tolerance + FLOAT_MARGIN

    return compare


def _sequence_within(tolerances: Sequence[float]) -> Comparator:
    def compare(wanted: Any, got: Any) -> bool:
        if isinstance(wanted, str) or isinstance(got, str):
            return False
        if not isinstance(wanted, Sequence) or not isinstance(got, Sequence):
            return False
        if len(wanted) != len(tolerances) or len(got) != len(tolerances):
            return False
        return all(
            _within(tolerance)(wanted_item, got_item)
            for wanted_item, got_item, tolerance in zip(
                wanted, got, tolerances, strict=True
            )
        )

    return compare


ATTRIBUTE_RULES: dict[str, dict[str, Comparator]] = {
    "light": {"brightness": _within(3), "effect": _exact},
    "cover": {"current_position": _within(3), "current_tilt_position": _within(3)},
    "fan": {
        "percentage": _within(3),
        "oscillating": _exact,
        "direction": _exact,
        "preset_mode": _exact,
    },
    "climate": {
        "temperature": _within(0.5),
        "target_temp_high": _within(0.5),
        "target_temp_low": _within(0.5),
        "preset_mode": _exact,
        "fan_mode": _exact,
        "swing_mode": _exact,
    },
    "media_player": {
        "volume_level": _within(0.02),
        "source": _exact,
        "sound_mode": _exact,
    },
    "humidifier": {"humidity": _within(2), "mode": _exact},
}

COLOR_MODE_ATTRIBUTES: dict[str, str] = {
    "color_temp": ATTR_COLOR_TEMP_KELVIN,
    "hs": "hs_color",
    "xy": "xy_color",
    "rgb": "rgb_color",
    "rgbw": "rgbw_color",
    "rgbww": "rgbww_color",
}

COLOR_ATTRIBUTE_ORDER: tuple[str, ...] = (
    ATTR_COLOR_TEMP_KELVIN,
    "hs_color",
    "rgb_color",
    "xy_color",
    "rgbw_color",
    "rgbww_color",
)

COLOR_COMPARATORS: dict[str, Comparator] = {
    ATTR_COLOR_TEMP_KELVIN: _within(50),
    "hs_color": _sequence_within((5, 5)),
    "xy_color": _sequence_within((0.02, 0.02)),
    "rgb_color": _sequence_within((5, 5, 5)),
    "rgbw_color": _sequence_within((5, 5, 5, 5)),
    "rgbww_color": _sequence_within((5, 5, 5, 5, 5)),
}


def _select_color_attribute(desired: Mapping[str, Any]) -> str | None:
    """Return the color attribute that carries the comparison, if any."""
    color_mode = desired.get(ATTR_COLOR_MODE)
    if color_mode is not None:
        return COLOR_MODE_ATTRIBUTES.get(str(color_mode))
    for attribute in COLOR_ATTRIBUTE_ORDER:
        if desired.get(attribute) is not None:
            return attribute
    return None


def _clamp_kelvin(wanted: Any, current: Mapping[str, Any]) -> Any:
    """Clamp the desired kelvin value to the range the light reports."""
    try:
        value = float(wanted)
    except TypeError, ValueError:
        return wanted
    low = current.get(ATTR_MIN_COLOR_TEMP_KELVIN)
    high = current.get(ATTR_MAX_COLOR_TEMP_KELVIN)
    if isinstance(low, int | float):
        value = max(value, float(low))
    if isinstance(high, int | float):
        value = min(value, float(high))
    return value


def _rules_for(desired: State) -> dict[str, Comparator]:
    rules = dict(ATTRIBUTE_RULES.get(desired.domain, {}))
    if desired.domain == "light":
        color_attribute = _select_color_attribute(desired.attributes)
        if color_attribute is not None:
            rules[color_attribute] = COLOR_COMPARATORS[color_attribute]
    return rules


def match_state(desired: State, current: State) -> MatchResult:
    """Return whether the current state satisfies the desired state."""
    if desired.state != current.state:
        return MatchResult(False, f"state: wanted {desired.state}, got {current.state}")
    if desired.state in STATES_WITHOUT_ATTRIBUTES:
        return MatchResult(True)

    for attribute, compare in _rules_for(desired).items():
        wanted = desired.attributes.get(attribute)
        if wanted is None:
            continue
        got = current.attributes.get(attribute)
        if got is None:
            return MatchResult(False, f"{attribute}: wanted {wanted}, got nothing")
        if attribute == ATTR_COLOR_TEMP_KELVIN:
            wanted = _clamp_kelvin(wanted, current.attributes)
        if not compare(wanted, got):
            return MatchResult(False, f"{attribute}: wanted {wanted}, got {got}")
    return MatchResult(True)
