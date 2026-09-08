"""Config flow for the Scene State integration."""

from collections.abc import Mapping
from typing import Any, override

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    wrapped_entity_config_entry_title,
)
import voluptuous as vol

from .const import (
    CONF_DEBOUNCE,
    CONF_GRACE_PERIOD,
    DEFAULT_DEBOUNCE,
    DEFAULT_GRACE_PERIOD,
    DOMAIN,
    MAX_DEBOUNCE,
    MAX_GRACE_PERIOD,
)


def _seconds_selector(maximum: float) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            max=maximum,
            step=0.5,
            unit_of_measurement="s",
            mode=selector.NumberSelectorMode.BOX,
        )
    )


TIMING_FIELDS = {
    vol.Required(CONF_GRACE_PERIOD, default=DEFAULT_GRACE_PERIOD): _seconds_selector(
        MAX_GRACE_PERIOD
    ),
    vol.Required(CONF_DEBOUNCE, default=DEFAULT_DEBOUNCE): _seconds_selector(
        MAX_DEBOUNCE
    ),
}

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="scene", integration="homeassistant")
        ),
        **TIMING_FIELDS,
    }
)

OPTIONS_SCHEMA = vol.Schema(TIMING_FIELDS)


async def _abort_if_scene_tracked(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Refuse a second entry for the same scene."""
    handler.parent_handler._async_abort_entries_match(  # noqa: SLF001
        {CONF_ENTITY_ID: user_input[CONF_ENTITY_ID]}
    )
    return user_input


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        CONFIG_SCHEMA, validate_user_input=_abort_if_scene_tracked
    ),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA),
}


class SceneStateConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle the config and options flow."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    options_flow_reloads = True

    VERSION = 1
    MINOR_VERSION = 1

    @override
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Use the friendly name of the scene as the entry title."""
        return wrapped_entity_config_entry_title(self.hass, options[CONF_ENTITY_ID])
