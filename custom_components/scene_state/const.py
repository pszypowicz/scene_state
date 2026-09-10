"""Constants for the Scene State integration."""

from typing import Final

from homeassistant.const import CONF_ENTITY_ID

DOMAIN: Final = "scene_state"

CONF_GRACE_PERIOD: Final = "grace_period"
CONF_DEBOUNCE: Final = "debounce"
CONF_COMPARE: Final = "compare"
CONF_CONFIGURE: Final = "configure"

DEFAULT_GRACE_PERIOD: Final = 5.0
DEFAULT_DEBOUNCE: Final = 1.0

MAX_GRACE_PERIOD: Final = 600.0
MAX_DEBOUNCE: Final = 60.0

# Every other top level option key is a domain name.
RESERVED_OPTION_KEYS: Final = frozenset(
    {CONF_ENTITY_ID, CONF_GRACE_PERIOD, CONF_DEBOUNCE}
)
