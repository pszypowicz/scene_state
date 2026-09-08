"""Tests for the state matching rules."""

from homeassistant.core import State
import pytest

from custom_components.scene_state.matching import MatchResult, match_state


def _light(state: str, **attributes: object) -> State:
    return State("light.test", state, attributes)


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
            _light("on", brightness=203),
            MatchResult(True),
            id="brightness_within_tolerance",
        ),
        pytest.param(
            _light("on", brightness=200),
            _light("on", brightness=204),
            MatchResult(False, "brightness: wanted 200, got 204"),
            id="brightness_outside_tolerance",
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
            _light("on", brightness="abc"),
            _light("on", brightness=10),
            MatchResult(False, "brightness: wanted abc, got 10"),
            id="malformed_value_is_mismatch",
        ),
        pytest.param(
            _light(
                "on", color_mode="color_temp", color_temp_kelvin=2700, hs_color=[30, 40]
            ),
            _light(
                "on",
                color_mode="color_temp",
                color_temp_kelvin=2750,
                hs_color=[200, 90],
            ),
            MatchResult(True),
            id="kelvin_within_tolerance_ignores_hs",
        ),
        pytest.param(
            _light("on", color_mode="color_temp", color_temp_kelvin=2700),
            _light("on", color_mode="color_temp", color_temp_kelvin=2751),
            MatchResult(False, "color_temp_kelvin: wanted 2700.0, got 2751"),
            id="kelvin_outside_tolerance",
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
            MatchResult(True),
            id="kelvin_clamped_to_light_range",
        ),
        pytest.param(
            _light("on", color_mode="hs", hs_color=[30, 40]),
            _light("on", color_mode="hs", hs_color=[35, 45]),
            MatchResult(True),
            id="hs_within_tolerance",
        ),
        pytest.param(
            _light("on", color_mode="hs", hs_color=[30, 40]),
            _light("on", color_mode="hs", hs_color=[36, 40]),
            MatchResult(False, "hs_color: wanted [30, 40], got [36, 40]"),
            id="hs_outside_tolerance",
        ),
        pytest.param(
            _light("on", color_mode="xy", xy_color=[0.3, 0.3]),
            _light("on", color_mode="xy", xy_color=[0.31, 0.29]),
            MatchResult(True),
            id="xy_within_tolerance",
        ),
        pytest.param(
            _light("on", color_mode="xy", xy_color=[0.3, 0.3]),
            _light("on", color_mode="xy", xy_color=[0.33, 0.3]),
            MatchResult(False, "xy_color: wanted [0.3, 0.3], got [0.33, 0.3]"),
            id="xy_outside_tolerance",
        ),
        pytest.param(
            _light("on", color_mode="rgb", rgb_color=[255, 0, 0]),
            _light("on", color_mode="rgb", rgb_color=[250, 5, 3]),
            MatchResult(True),
            id="rgb_within_tolerance",
        ),
        pytest.param(
            _light("on", color_mode="rgb", rgb_color=[255, 0, 0]),
            _light("on", color_mode="rgb", rgb_color=[249, 0, 0]),
            MatchResult(False, "rgb_color: wanted [255, 0, 0], got [249, 0, 0]"),
            id="rgb_outside_tolerance",
        ),
        pytest.param(
            _light("on", color_mode="rgbww", rgbww_color=[10, 20, 30, 40, 50]),
            _light("on", color_mode="rgbww", rgbww_color=[15, 25, 35, 45, 55]),
            MatchResult(True),
            id="rgbww_within_tolerance",
        ),
        pytest.param(
            _light("on", color_temp_kelvin=2700, hs_color=[30, 40]),
            _light("on", color_temp_kelvin=2720, hs_color=[200, 90]),
            MatchResult(True),
            id="no_color_mode_prefers_kelvin",
        ),
        pytest.param(
            _light("on", hs_color=[30, 40], xy_color=[0.9, 0.9]),
            _light("on", hs_color=[31, 41], xy_color=[0.1, 0.1]),
            MatchResult(True),
            id="no_color_mode_prefers_hs_over_xy",
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
            _light("on", color_mode="hs", hs_color=[30]),
            _light("on", color_mode="hs", hs_color=[30, 40]),
            MatchResult(False, "hs_color: wanted [30], got [30, 40]"),
            id="list_length_mismatch",
        ),
        pytest.param(
            _light("on", effect="rainbow"),
            _light("on", effect="Rainbow"),
            MatchResult(False, "effect: wanted rainbow, got Rainbow"),
            id="effect_exact",
        ),
        pytest.param(
            State("cover.test", "open", {"current_position": 50}),
            State("cover.test", "open", {"current_position": 47}),
            MatchResult(True),
            id="cover_position_within_tolerance",
        ),
        pytest.param(
            State("cover.test", "open", {"current_position": 50}),
            State("cover.test", "open", {"current_position": 46}),
            MatchResult(False, "current_position: wanted 50, got 46"),
            id="cover_position_outside_tolerance",
        ),
        pytest.param(
            State("fan.test", "on", {"percentage": 33, "oscillating": True}),
            State("fan.test", "on", {"percentage": 35, "oscillating": True}),
            MatchResult(True),
            id="fan_within_tolerance",
        ),
        pytest.param(
            State("fan.test", "on", {"oscillating": True}),
            State("fan.test", "on", {"oscillating": False}),
            MatchResult(False, "oscillating: wanted True, got False"),
            id="fan_oscillating_exact",
        ),
        pytest.param(
            State("climate.test", "heat", {"temperature": 21}),
            State(
                "climate.test", "heat", {"temperature": 21.5, "current_temperature": 15}
            ),
            MatchResult(True),
            id="climate_target_within_tolerance",
        ),
        pytest.param(
            State("climate.test", "heat", {"temperature": 21}),
            State("climate.test", "heat", {"temperature": 21.6}),
            MatchResult(False, "temperature: wanted 21, got 21.6"),
            id="climate_target_outside_tolerance",
        ),
        pytest.param(
            State("media_player.test", "playing", {"volume_level": 0.3}),
            State("media_player.test", "playing", {"volume_level": 0.32}),
            MatchResult(True),
            id="volume_within_tolerance",
        ),
        pytest.param(
            State("media_player.test", "playing", {"volume_level": 0.3}),
            State("media_player.test", "playing", {"volume_level": 0.33}),
            MatchResult(False, "volume_level: wanted 0.3, got 0.33"),
            id="volume_outside_tolerance",
        ),
        pytest.param(
            State("humidifier.test", "on", {"humidity": 50, "mode": "auto"}),
            State("humidifier.test", "on", {"humidity": 52, "mode": "auto"}),
            MatchResult(True),
            id="humidifier_within_tolerance",
        ),
        pytest.param(
            State("switch.test", "on", {"brightness": 1}),
            State("switch.test", "on", {"brightness": 999}),
            MatchResult(True),
            id="domain_without_rules_compares_state_only",
        ),
        pytest.param(
            _light("on", brightness=10, friendly_name="Desired", supported_features=1),
            _light("on", brightness=10, friendly_name="Current", supported_features=2),
            MatchResult(True),
            id="unknown_attributes_ignored",
        ),
    ],
)
def test_match_state(desired: State, current: State, expected: MatchResult) -> None:
    """Compare a desired scene state with a current entity state."""
    assert match_state(desired, current) == expected
