"""Binary sensor that reports whether a scene is active."""

from typing import Any, override

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_DEBOUNCE, CONF_GRACE_PERIOD
from .matching import MatchProfile
from .tracker import SceneStatus, SceneTracker

ATTR_SCENE_ENTITY_ID = "scene_entity_id"
ATTR_MISMATCHED_ENTITIES = "mismatched_entities"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the sensor for the config entry."""
    async_add_entities([SceneStateBinarySensor(hass, entry)])


class SceneStateBinarySensor(BinarySensorEntity):
    """On while every member of the scene matches the scene."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Create the tracker for the configured scene."""
        self._attr_unique_id = entry.entry_id
        self._attr_name = entry.title
        self._tracker = SceneTracker(
            hass,
            entry.options[CONF_ENTITY_ID],
            float(entry.options[CONF_GRACE_PERIOD]),
            float(entry.options[CONF_DEBOUNCE]),
            MatchProfile.from_options(entry.options),
            self._handle_tracker_update,
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Start tracking once the entity has an entity ID."""
        await super().async_added_to_hass()
        self._tracker.async_start()
        self.async_on_remove(self._tracker.async_stop)

    @callback
    def _handle_tracker_update(self) -> None:
        self.async_write_ha_state()

    @property
    @override
    def available(self) -> bool:
        """Return False while the scene entity is not loaded."""
        return self._tracker.status is not SceneStatus.SCENE_MISSING

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the aggregate result, None for unknown."""
        if self._tracker.status is SceneStatus.ACTIVE:
            return True
        if self._tracker.status is SceneStatus.INACTIVE:
            return False
        return None

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the tracked scene and the mismatched members."""
        return {
            ATTR_SCENE_ENTITY_ID: self._tracker.scene_entity_id,
            ATTR_MISMATCHED_ENTITIES: list(self._tracker.mismatched),
        }
