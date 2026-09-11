"""Constants for the Scene State integration."""

from typing import Final

from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_NAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)

DOMAIN: Final = "scene_state"

UNKNOWN_STATES: Final = frozenset({STATE_UNAVAILABLE, STATE_UNKNOWN})

CONF_GRACE_PERIOD: Final = "grace_period"
CONF_DEBOUNCE: Final = "debounce"
CONF_COMPARE: Final = "compare"
CONF_CONFIGURE: Final = "configure"

DEFAULT_GRACE_PERIOD: Final = 5.0
DEFAULT_DEBOUNCE: Final = 1.0

MAX_GRACE_PERIOD: Final = 600.0
MAX_DEBOUNCE: Final = 60.0

# A key that is not reserved and holds a mapping with a compare list is read as
# a domain rule.
RESERVED_OPTION_KEYS: Final = frozenset(
    {CONF_ENTITY_ID, CONF_NAME, CONF_GRACE_PERIOD, CONF_DEBOUNCE, CONF_CONFIGURE}
)
