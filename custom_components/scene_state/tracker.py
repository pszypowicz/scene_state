"""Track whether the members of a scene match the scene."""

from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
import logging

from homeassistant.core import (
    CALLBACK_TYPE,
    CoreState,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
)
from homeassistant.helpers.start import async_at_started

from .const import UNKNOWN_STATES
from .matching import MatchProfile, match_state
from .scene_source import get_scene_targets

_LOGGER = logging.getLogger(__name__)


class SceneStatus(StrEnum):
    """Aggregate result of one evaluation."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    UNKNOWN = "unknown"
    SCENE_MISSING = "scene_missing"


class SceneTracker:
    """Evaluate a scene against the current member states."""

    def __init__(
        self,
        hass: HomeAssistant,
        scene_entity_id: str,
        grace_period: float,
        debounce: float,
        profile: MatchProfile,
        on_update: Callable[[], None],
    ) -> None:
        """Initialize the tracker without subscribing."""
        self._hass = hass
        self._scene_entity_id = scene_entity_id
        self._grace_period = grace_period
        self._debounce = debounce
        self._profile = profile
        self._on_update = on_update
        self.status = SceneStatus.SCENE_MISSING
        self.mismatched: list[str] = []
        self._members: frozenset[str] = frozenset()
        self._unsub_members: CALLBACK_TYPE | None = None
        self._unsub_scene: CALLBACK_TYPE | None = None
        self._unsub_started: CALLBACK_TYPE | None = None
        self._cancel_debounce: CALLBACK_TYPE | None = None
        self._cancel_grace: CALLBACK_TYPE | None = None
        self._started = False

    @property
    def scene_entity_id(self) -> str:
        """Return the tracked scene entity ID."""
        return self._scene_entity_id

    @callback
    def async_start(self) -> None:
        """Subscribe to the scene entity and run the first evaluation."""
        if self._started:
            return
        self._started = True
        self._unsub_scene = async_track_state_change_event(
            self._hass, [self._scene_entity_id], self._handle_scene_event
        )
        self.async_evaluate()
        if self._hass.state is not CoreState.running:
            # The built-in scene platform publishes its data after its entities
            # exist, so an evaluation during startup can miss a scene that is
            # still loading. One more evaluation after startup closes that window.
            self._unsub_started = async_at_started(self._hass, self._handle_started)

    @callback
    def async_stop(self) -> None:
        """Cancel timers and remove subscriptions."""
        self._started = False
        self._cancel_timers()
        if self._unsub_started is not None:
            self._unsub_started()
            self._unsub_started = None
        self._subscribe_members(frozenset())
        if self._unsub_scene is not None:
            self._unsub_scene()
            self._unsub_scene = None

    @callback
    def _handle_started(self, _hass: HomeAssistant) -> None:
        self._unsub_started = None
        self.async_evaluate()

    @callback
    def async_evaluate(self) -> None:
        """Compare every member with its target and update the status."""
        if not self._started:
            return
        targets = get_scene_targets(self._hass, self._scene_entity_id)
        if targets is None:
            self._subscribe_members(frozenset())
            self.status = SceneStatus.SCENE_MISSING
            self.mismatched = []
            self._on_update()
            return

        self._subscribe_members(frozenset(targets))
        mismatched: list[str] = []
        unknown = False
        for entity_id, desired in targets.items():
            current = self._hass.states.get(entity_id)
            if current is None or current.state in UNKNOWN_STATES:
                unknown = True
                continue
            result = match_state(desired, current, self._profile)
            if not result.matches:
                _LOGGER.debug(
                    "%s: %s does not match, %s",
                    self._scene_entity_id,
                    entity_id,
                    result.reason,
                )
                mismatched.append(entity_id)

        self.mismatched = sorted(mismatched)
        if mismatched:
            self.status = SceneStatus.INACTIVE
        elif unknown:
            self.status = SceneStatus.UNKNOWN
        else:
            self.status = SceneStatus.ACTIVE
        self._on_update()

    def _subscribe_members(self, members: frozenset[str]) -> None:
        if members == self._members:
            return
        if self._unsub_members is not None:
            self._unsub_members()
            self._unsub_members = None
        self._members = members
        if members:
            self._unsub_members = async_track_state_change_event(
                self._hass, list(members), self._handle_member_event
            )

    @callback
    def _handle_member_event(self, event: Event[EventStateChangedData]) -> None:
        if self._cancel_grace is not None:
            return
        if self._debounce <= 0:
            self.async_evaluate()
            return
        if self._cancel_debounce is not None:
            self._cancel_debounce()
        self._cancel_debounce = async_call_later(
            self._hass, self._debounce, self._handle_debounce_expired
        )

    @callback
    def _handle_scene_event(self, event: Event[EventStateChangedData]) -> None:
        new_state = event.data["new_state"]
        old_state = event.data["old_state"]
        if new_state is None or new_state.state in UNKNOWN_STATES:
            # The scene was removed, reloaded, or never activated. Re-read the
            # targets right away, there is no transition to wait for.
            self._cancel_timers()
            self.async_evaluate()
            return
        if old_state is not None and old_state.state == new_state.state:
            return
        if self._cancel_debounce is not None:
            self._cancel_debounce()
            self._cancel_debounce = None
        if self._grace_period <= 0:
            self.async_evaluate()
            return
        if self._cancel_grace is not None:
            self._cancel_grace()
        self._cancel_grace = async_call_later(
            self._hass, self._grace_period, self._handle_grace_expired
        )

    @callback
    def _handle_debounce_expired(self, _now: datetime) -> None:
        self._cancel_debounce = None
        self.async_evaluate()

    @callback
    def _handle_grace_expired(self, _now: datetime) -> None:
        self._cancel_grace = None
        self.async_evaluate()

    def _cancel_timers(self) -> None:
        if self._cancel_debounce is not None:
            self._cancel_debounce()
            self._cancel_debounce = None
        if self._cancel_grace is not None:
            self._cancel_grace()
            self._cancel_grace = None
