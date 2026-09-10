"""Tests for the state matching rules."""

from typing import Any

from homeassistant.core import State
import pytest

from custom_components.scene_state.matching import (
    MatchProfile,
    MatchResult,
    match_state,
)

EXACT = MatchProfile.from_options({})


def _light(state: str, **attributes: Any) -> State:
    return State("light.test", state, attributes)


def _profile(domain: str, compare: list[str], **tolerances: float) -> MatchProfile:
    return MatchProfile.from_options({domain: {"compare": compare, **tolerances}})


@pytest.mark.parametrize(
    ("desired", "current", "expected"),
    [
        pytest.param(
            _light("on"),
            _light("off"),
            MatchResult(False, "state: wanted on, got off"),
            id="state_mismatch",
        ),
        pytest.param(
            _light("off", brightness=200),
            _light("off", brightness=10),
            MatchResult(True),
            id="off_ignores_attributes",
        ),
        pytest.param(
            State("cover.test", "closed", {"current_position": 0}),
            State("cover.test", "closed", {"current_position": 5}),
            MatchResult(True),
            id="closed_ignores_attributes",
        ),
        pytest.param(
            _light("on", brightness=200),
            _light("on", brightness=200),
            MatchResult(True),
            id="equal_brightness_matches",
        ),
        pytest.param(
            _light("on", brightness=200),
            _light("on", brightness=201),
            MatchResult(False, "brightness: wanted 200, got 201"),
            id="brightness_off_by_one_is_mismatch",
        ),
        pytest.param(
            _light("on", brightness=200),
            _light("on"),
            MatchResult(False, "brightness: wanted 200, got nothing"),
            id="missing_attribute_is_mismatch",
        ),
        pytest.param(
            _light("on", brightness=None),
            _light("on"),
            MatchResult(True),
            id="none_desired_ignored",
        ),
        pytest.param(
            _light(
                "on", color_mode="color_temp", color_temp_kelvin=2700, hs_color=[30, 40]
            ),
            _light(
                "on",
                color_mode="color_temp",
                color_temp_kelvin=2700,
                hs_color=[200, 90],
            ),
            MatchResult(True),
            id="selected_representation_ignores_the_rest",
        ),
        pytest.param(
            _light("on", color_mode="color_temp", color_temp_kelvin=2000),
            _light(
                "on",
                color_mode="color_temp",
                color_temp_kelvin=2200,
                min_color_temp_kelvin=2200,
                max_color_temp_kelvin=6500,
            ),
            MatchResult(False, "color_temp_kelvin: wanted 2000, got 2200"),
            id="kelvin_is_not_clamped",
        ),
        pytest.param(
            _light("on", color_mode="hs", hs_color=[30, 40]),
            _light("on", color_mode="hs", hs_color=(30.0, 40.0)),
            MatchResult(True),
            id="equal_sequence_across_types_matches",
        ),
        pytest.param(
            _light("on", color_mode="hs", hs_color=[30, 40]),
            _light("on", color_mode="hs", hs_color=[30]),
            MatchResult(False, "hs_color: wanted [30, 40], got [30]"),
            id="sequence_length_mismatch",
        ),
        pytest.param(
            _light("on", color_mode="hs", hs_color=[30, 40]),
            _light("on", color_mode="color_temp", color_temp_kelvin=2700),
            MatchResult(False, "hs_color: wanted [30, 40], got nothing"),
            id="missing_color_attribute_is_mismatch",
        ),
        pytest.param(
            _light("on", color_mode="white", brightness=100, hs_color=[30, 40]),
            _light("on", color_mode="white", brightness=100),
            MatchResult(True),
            id="white_mode_compares_no_color",
        ),
        pytest.param(
            _light("on", effect="rainbow"),
            _light("on", effect="Rainbow"),
            MatchResult(False, "effect: wanted rainbow, got Rainbow"),
            id="effect_exact",
        ),
        pytest.param(
            State("switch.test", "on", {"custom": 1}),
            State("switch.test", "on", {"custom": 999}),
            MatchResult(False, "custom: wanted 1, got 999"),
            id="any_domain_compares_its_attributes",
        ),
        pytest.param(
            _light("on", brightness=10, friendly_name="Desired", supported_features=1),
            _light("on", brightness=10, friendly_name="Current", supported_features=2),
            MatchResult(True),
            id="metadata_ignored",
        ),
        pytest.param(
            State("fan.test", "on", {"oscillating": True}),
            State("fan.test", "on", {"oscillating": False}),
            MatchResult(False, "oscillating: wanted True, got False"),
            id="oscillating_exact",
        ),
        pytest.param(
            _light("on", brightness="abc"),
            _light("on", brightness=10),
            MatchResult(False, "brightness: wanted abc, got 10"),
            id="non_numeric_desired_against_a_number",
        ),
        pytest.param(
            State("climate.test", "heat", {"temperature": 21}),
            State(
                "climate.test", "heat", {"temperature": 21, "current_temperature": 15}
            ),
            MatchResult(True),
            id="extra_current_attribute_ignored",
        ),
        pytest.param(
            _light("on", brightness=200.5),
            _light("on", brightness=201.5),
            MatchResult(False, "brightness: wanted 200.5, got 201.5"),
            id="reason_renders_a_float",
        ),
        pytest.param(
            State("switch.test", "on", {"custom": "100"}),
            State("switch.test", "on", {"custom": 100}),
            MatchResult(True),
            id="quoted_number_matches_numeric_value",
        ),
    ],
)
def test_exact_profile(desired: State, current: State, expected: MatchResult) -> None:
    """Without stored rules every comparable attribute compares exactly."""
    assert match_state(desired, current, EXACT) == expected


@pytest.mark.parametrize(
    ("desired", "current", "profile", "expected"),
    [
        pytest.param(
            _light("on", brightness=200),
            _light("on", brightness=203),
            _profile("light", ["brightness"], brightness=3),
            MatchResult(True),
            id="tolerance_boundary_is_inclusive",
        ),
        pytest.param(
            _light("on", brightness=200),
            _light("on", brightness=204),
            _profile("light", ["brightness"], brightness=3),
            MatchResult(False, "brightness: wanted 200, got 204"),
            id="tolerance_outside",
        ),
        pytest.param(
            _light("on", brightness=200, effect="rainbow"),
            _light("on", brightness=200, effect="none"),
            _profile("light", ["brightness"]),
            MatchResult(True),
            id="unselected_attribute_ignored",
        ),
        pytest.param(
            _light("on", brightness=200),
            _light("on", brightness=1),
            _profile("light", []),
            MatchResult(True),
            id="empty_selection_compares_state_only",
        ),
        pytest.param(
            _light("on", color_mode="hs", hs_color=[30, 40]),
            _light("on", color_mode="hs", hs_color=[33, 44]),
            _profile("light", ["color"], hs_color=4),
            MatchResult(True),
            id="color_selection_covers_the_representation",
        ),
        pytest.param(
            _light("on", color_mode="hs", hs_color=[30, 40]),
            _light("on", color_mode="hs", hs_color=[99, 99]),
            _profile("light", ["brightness"]),
            MatchResult(True),
            id="color_not_selected_is_ignored",
        ),
        pytest.param(
            _light("on", effect="rainbow"),
            _light("on", effect="none"),
            _profile("light", ["effect"], effect=5),
            MatchResult(False, "effect: wanted rainbow, got none"),
            id="tolerance_on_a_string_is_a_mismatch",
        ),
        pytest.param(
            State("cover.test", "open", {"current_position": 70}),
            State("cover.test", "open", {"current_position": 68}),
            _profile("cover", ["current_position"], current_position=2),
            MatchResult(True),
            id="cover_tolerance",
        ),
        pytest.param(
            State("media_player.test", "playing", {"volume_level": 0.3}),
            State("media_player.test", "playing", {"volume_level": 0.32}),
            _profile("media_player", ["volume_level"], volume_level=0.02),
            MatchResult(True),
            id="float_tolerance_survives_rounding",
        ),
        pytest.param(
            _light("on", brightness=200),
            _light("on", brightness=204),
            _profile("cover", ["current_position"], current_position=99),
            MatchResult(False, "brightness: wanted 200, got 204"),
            id="another_domain_does_not_leak",
        ),
        pytest.param(
            State("fan.test", "on", {"oscillating": True}),
            State("fan.test", "on", {"oscillating": False}),
            _profile("fan", ["oscillating"], oscillating=1),
            MatchResult(False, "oscillating: wanted True, got False"),
            id="tolerance_does_not_bridge_a_boolean",
        ),
        pytest.param(
            _light("on", color_mode="rgb", rgb_color=[10, 20, 30]),
            _light("on", color_mode="rgb", rgb_color=[12, 18, 33]),
            _profile("light", ["color"], rgb_color=5),
            MatchResult(True),
            id="rgb_color_tolerance",
        ),
        pytest.param(
            _light("on", color_mode="rgbw", rgbw_color=[10, 20, 30, 40]),
            _light("on", color_mode="rgbw", rgbw_color=[12, 18, 33, 44]),
            _profile("light", ["color"], rgbw_color=5),
            MatchResult(True),
            id="rgbw_color_tolerance",
        ),
        pytest.param(
            _light("on", color_mode="rgbww", rgbww_color=[10, 20, 30, 40, 50]),
            _light("on", color_mode="rgbww", rgbww_color=[12, 18, 33, 44, 47]),
            _profile("light", ["color"], rgbww_color=5),
            MatchResult(True),
            id="rgbww_color_tolerance",
        ),
    ],
)
def test_stored_profile(
    desired: State, current: State, profile: MatchProfile, expected: MatchResult
) -> None:
    """Stored rules select the attributes and widen the comparison."""
    assert match_state(desired, current, profile) == expected


@pytest.mark.parametrize(
    "options",
    [
        pytest.param({}, id="empty"),
        pytest.param({"entity_id": "scene.a"}, id="reserved_key"),
        pytest.param({"grace_period": 5.0, "debounce": 1.0}, id="reserved_numbers"),
        pytest.param({"light": "not a mapping"}, id="value_is_not_a_mapping"),
        pytest.param({"light": {"brightness": 3}}, id="mapping_without_compare"),
    ],
)
def test_from_options_ignores_unusable_keys(options: dict[str, Any]) -> None:
    """An option that is not a domain rule leaves the profile empty."""
    profile = MatchProfile.from_options(options)
    assert profile.compare == {}
    assert profile.compares("light", "brightness") is True
    assert profile.tolerance("light", "brightness") is None


def test_from_options_reads_a_domain_rule() -> None:
    """A domain mapping yields a selection and its tolerances."""
    profile = MatchProfile.from_options(
        {
            "entity_id": "scene.a",
            "light": {"compare": ["brightness", "color"], "brightness": 4},
        }
    )
    assert profile.compare == {"light": frozenset({"brightness", "color"})}
    assert profile.tolerance("light", "brightness") == 4.0
    assert profile.tolerance("light", "hs_color") is None
    assert profile.compares("light", "hs_color") is True
    assert profile.compares("light", "effect") is False


def test_boolean_tolerance_is_excluded() -> None:
    """A boolean stored as a number does not become a tolerance."""
    profile = MatchProfile.from_options(
        {"light": {"compare": ["brightness"], "brightness": True}}
    )
    assert profile.tolerance("light", "brightness") is None
