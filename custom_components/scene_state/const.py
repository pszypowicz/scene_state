"""Constants for the Scene State integration."""

from typing import Final

DOMAIN: Final = "scene_state"

CONF_GRACE_PERIOD: Final = "grace_period"
CONF_DEBOUNCE: Final = "debounce"

DEFAULT_GRACE_PERIOD: Final = 5.0
DEFAULT_DEBOUNCE: Final = 1.0

MAX_GRACE_PERIOD: Final = 600.0
MAX_DEBOUNCE: Final = 60.0
