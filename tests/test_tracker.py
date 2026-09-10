"""Tests for the scene tracker."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_fire_time_changed_exact

from custom_components.scene_state.matching import MatchProfile
from custom_components.scene_state.tracker import SceneStatus, SceneTracker

SCENE_ENTITY_ID = "scene.movie"
MOVIE_SCENE = {
    "name": "Movie",
    "entities": {
        "light.a": {"state": "on", "brightness": 100},
        "switch.b": "off",
    },
}
ACTIVATED = "2026-09-08T10:00:00+00:00"
ACTIVATED_AGAIN = "2026-09-08T10:05:00+00:00"


async def _setup_scene(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, "scene", {"scene": [MOVIE_SCENE]})
    await hass.async_block_till_done()


def _set_members_matching(hass: HomeAssistant) -> None:
    hass.states.async_set("light.a", "on", {"brightness": 100})
    hass.states.async_set("switch.b", "off")


def _make_tracker(
    hass: HomeAssistant,
    updates: list[SceneStatus],
    grace_period: float = 5.0,
    debounce: float = 1.0,
    profile: MatchProfile | None = None,
) -> SceneTracker:
    tracker = SceneTracker(
        hass,
        SCENE_ENTITY_ID,
        grace_period,
        debounce,
        profile if profile is not None else MatchProfile.from_options({}),
        lambda: updates.append(tracker.status),
    )
    return tracker


async def _advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float
) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed_exact(hass)
    await hass.async_block_till_done()


async def test_initial_evaluation_is_active(hass: HomeAssistant) -> None:
    """All members match at start."""
    await _setup_scene(hass)
    _set_members_matching(hass)
    updates: list[SceneStatus] = []
    tracker = _make_tracker(hass, updates)

    tracker.async_start()

    assert tracker.status is SceneStatus.ACTIVE
    assert tracker.mismatched == []
    assert updates == [SceneStatus.ACTIVE]
    tracker.async_stop()


async def test_missing_member_is_unknown(hass: HomeAssistant) -> None:
    """A member without a state makes the result unknown."""
    await _setup_scene(hass)
    hass.states.async_set("light.a", "on", {"brightness": 100})
    tracker = _make_tracker(hass, [])

    tracker.async_start()

    assert tracker.status is SceneStatus.UNKNOWN
    assert tracker.mismatched == []
    tracker.async_stop()


async def test_unavailable_member_is_unknown(hass: HomeAssistant) -> None:
    """An unavailable member makes the result unknown."""
    await _setup_scene(hass)
    hass.states.async_set("light.a", "on", {"brightness": 100})
    hass.states.async_set("switch.b", "unavailable")
    tracker = _make_tracker(hass, [])

    tracker.async_start()

    assert tracker.status is SceneStatus.UNKNOWN
    tracker.async_stop()


async def test_mismatch_wins_over_unknown(hass: HomeAssistant) -> None:
    """A mismatch is reported even when another member is unknown."""
    await _setup_scene(hass)
    hass.states.async_set("light.a", "on", {"brightness": 10})
    tracker = _make_tracker(hass, [])

    tracker.async_start()

    assert tracker.status is SceneStatus.INACTIVE
    assert tracker.mismatched == ["light.a"]
    tracker.async_stop()


async def test_scene_missing(hass: HomeAssistant) -> None:
    """Without the scene the tracker reports scene missing."""
    tracker = _make_tracker(hass, [])

    tracker.async_start()

    assert tracker.status is SceneStatus.SCENE_MISSING
    tracker.async_stop()


async def test_debounce_restarts_on_new_event(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Only one evaluation runs after the last member change."""
    await _setup_scene(hass)
    _set_members_matching(hass)
    updates: list[SceneStatus] = []
    tracker = _make_tracker(hass, updates)
    tracker.async_start()

    hass.states.async_set("light.a", "on", {"brightness": 10})
    await _advance(hass, freezer, 0.6)
    assert updates == [SceneStatus.ACTIVE]

    hass.states.async_set("light.a", "on", {"brightness": 20})
    await _advance(hass, freezer, 0.6)
    assert updates == [SceneStatus.ACTIVE]

    await _advance(hass, freezer, 0.5)
    assert updates == [SceneStatus.ACTIVE, SceneStatus.INACTIVE]
    assert tracker.mismatched == ["light.a"]
    tracker.async_stop()


async def test_debounce_zero_evaluates_immediately(hass: HomeAssistant) -> None:
    """A debounce of zero evaluates on every member event."""
    await _setup_scene(hass)
    _set_members_matching(hass)
    updates: list[SceneStatus] = []
    tracker = _make_tracker(hass, updates, debounce=0.0)
    tracker.async_start()

    hass.states.async_set("light.a", "on", {"brightness": 10})
    await hass.async_block_till_done()

    assert updates == [SceneStatus.ACTIVE, SceneStatus.INACTIVE]
    tracker.async_stop()


async def test_grace_period_absorbs_member_events(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Member changes during the grace period wait for its end."""
    await _setup_scene(hass)
    _set_members_matching(hass)
    updates: list[SceneStatus] = []
    tracker = _make_tracker(hass, updates)
    tracker.async_start()

    hass.states.async_set(SCENE_ENTITY_ID, ACTIVATED)
    await hass.async_block_till_done()
    hass.states.async_set("light.a", "on", {"brightness": 10})
    await _advance(hass, freezer, 2.0)
    assert updates == [SceneStatus.ACTIVE]

    hass.states.async_set("light.a", "on", {"brightness": 100})
    await _advance(hass, freezer, 3.5)

    assert updates == [SceneStatus.ACTIVE, SceneStatus.ACTIVE]
    tracker.async_stop()


async def test_activation_cancels_pending_debounce(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """An activation replaces a running debounce with the grace period."""
    await _setup_scene(hass)
    _set_members_matching(hass)
    updates: list[SceneStatus] = []
    tracker = _make_tracker(hass, updates)
    tracker.async_start()

    hass.states.async_set("light.a", "on", {"brightness": 10})
    await hass.async_block_till_done()
    hass.states.async_set(SCENE_ENTITY_ID, ACTIVATED)
    await _advance(hass, freezer, 1.5)
    assert updates == [SceneStatus.ACTIVE]

    await _advance(hass, freezer, 4.0)

    assert updates == [SceneStatus.ACTIVE, SceneStatus.INACTIVE]
    tracker.async_stop()


async def test_second_activation_restarts_grace(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A new timestamp restarts the grace period."""
    await _setup_scene(hass)
    _set_members_matching(hass)
    updates: list[SceneStatus] = []
    tracker = _make_tracker(hass, updates)
    tracker.async_start()

    hass.states.async_set(SCENE_ENTITY_ID, ACTIVATED)
    await _advance(hass, freezer, 4.0)
    hass.states.async_set(SCENE_ENTITY_ID, ACTIVATED_AGAIN)
    await _advance(hass, freezer, 4.0)
    assert updates == [SceneStatus.ACTIVE]

    await _advance(hass, freezer, 1.5)

    assert updates == [SceneStatus.ACTIVE, SceneStatus.ACTIVE]
    tracker.async_stop()


async def test_reload_replaces_member_subscription(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """After a reload the tracker follows the new members only."""
    await _setup_scene(hass)
    _set_members_matching(hass)
    updates: list[SceneStatus] = []
    tracker = _make_tracker(hass, updates, grace_period=0.0)
    tracker.async_start()

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={
            "scene": {"name": "Movie", "entities": {"light.a": "on", "switch.c": "on"}}
        },
    ):
        await hass.services.async_call("scene", "reload", blocking=True)
        await hass.async_block_till_done()
    assert tracker.status is SceneStatus.UNKNOWN
    evaluations_after_reload = len(updates)

    hass.states.async_set("switch.b", "on")
    await _advance(hass, freezer, 1.5)
    assert len(updates) == evaluations_after_reload

    hass.states.async_set("switch.c", "on")
    await _advance(hass, freezer, 1.5)

    assert len(updates) == evaluations_after_reload + 1
    assert tracker.status is SceneStatus.ACTIVE
    tracker.async_stop()


async def test_reload_without_scene_sets_missing(hass: HomeAssistant) -> None:
    """A reload that drops the scene makes the tracker report scene missing."""
    await _setup_scene(hass)
    _set_members_matching(hass)
    tracker = _make_tracker(hass, [], grace_period=0.0)
    tracker.async_start()

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={"scene": {"name": "Other", "entities": {"light.a": "on"}}},
    ):
        await hass.services.async_call("scene", "reload", blocking=True)
        await hass.async_block_till_done()

    assert tracker.status is SceneStatus.SCENE_MISSING
    tracker.async_stop()


async def test_stop_cancels_pending_timers(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """No update arrives after the tracker is stopped."""
    await _setup_scene(hass)
    _set_members_matching(hass)
    updates: list[SceneStatus] = []
    tracker = _make_tracker(hass, updates)
    tracker.async_start()
    hass.states.async_set("light.a", "on", {"brightness": 10})
    await hass.async_block_till_done()

    tracker.async_stop()
    await _advance(hass, freezer, 2.0)
    hass.states.async_set("light.a", "on", {"brightness": 20})
    await _advance(hass, freezer, 2.0)

    assert updates == [SceneStatus.ACTIVE]


async def test_scene_loaded_during_startup_is_tracked_after_start(
    hass: HomeAssistant,
) -> None:
    """A tracker started before the scene platform recovers once startup ends."""
    hass.set_state(CoreState.starting)
    _set_members_matching(hass)
    updates: list[SceneStatus] = []
    tracker = _make_tracker(hass, updates, grace_period=0.0)
    tracker.async_start()
    assert tracker.status is SceneStatus.SCENE_MISSING

    await _setup_scene(hass)
    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert tracker.status is SceneStatus.ACTIVE
    tracker.async_stop()


async def test_stop_removes_scene_subscription(hass: HomeAssistant) -> None:
    """A scene state change after stop produces no update."""
    await _setup_scene(hass)
    _set_members_matching(hass)
    updates: list[SceneStatus] = []
    tracker = _make_tracker(hass, updates, grace_period=0.0)
    tracker.async_start()

    tracker.async_stop()
    hass.states.async_set(SCENE_ENTITY_ID, ACTIVATED)
    await hass.async_block_till_done()

    assert updates == [SceneStatus.ACTIVE]


async def test_evaluate_after_stop_is_ignored(hass: HomeAssistant) -> None:
    """An evaluation request after stop neither updates nor resubscribes."""
    await _setup_scene(hass)
    _set_members_matching(hass)
    updates: list[SceneStatus] = []
    tracker = _make_tracker(hass, updates, debounce=0.0)
    tracker.async_start()

    tracker.async_stop()
    tracker.async_evaluate()
    hass.states.async_set("light.a", "on", {"brightness": 10})
    await hass.async_block_till_done()

    assert updates == [SceneStatus.ACTIVE]


async def test_profile_changes_the_status(hass: HomeAssistant) -> None:
    """The same member state gives a different status under two profiles."""
    await _setup_scene(hass)
    hass.states.async_set("light.a", "on", {"brightness": 103})
    hass.states.async_set("switch.b", "off")

    strict = _make_tracker(hass, [])
    strict.async_start()
    assert strict.status is SceneStatus.INACTIVE
    strict.async_stop()

    lenient = _make_tracker(
        hass,
        [],
        profile=MatchProfile.from_options(
            {"light": {"compare": ["brightness"], "brightness": 3}}
        ),
    )
    lenient.async_start()
    assert lenient.status is SceneStatus.ACTIVE
    lenient.async_stop()
