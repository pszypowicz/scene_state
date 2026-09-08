"""Read the target states of a scene from the built-in scene platform."""

from typing import cast

from homeassistant.components.homeassistant.scene import (
    DATA_PLATFORM,
    HomeAssistantScene,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.entity_platform import EntityPlatform


@callback
def get_scene_targets(
    hass: HomeAssistant, scene_entity_id: str
) -> dict[str, State] | None:
    """Return the desired state per member, or None when the scene is not loaded.

    Core reads the same platform data for its entities_in_scene helper. This is
    the only module that depends on it.
    """
    platform: EntityPlatform | None = hass.data.get(DATA_PLATFORM)
    if platform is None:
        return None
    entity = platform.entities.get(scene_entity_id)
    if entity is None:
        return None
    scene = cast(HomeAssistantScene, entity)
    return dict(scene.scene_config.states)
