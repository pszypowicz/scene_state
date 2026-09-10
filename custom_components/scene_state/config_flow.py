"""Config flow for the Scene State integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import State
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    wrapped_entity_config_entry_title,
)
import voluptuous as vol

from .attributes import comparable, selection_name
from .const import (
    CONF_COMPARE,
    CONF_CONFIGURE,
    CONF_DEBOUNCE,
    CONF_GRACE_PERIOD,
    DEFAULT_DEBOUNCE,
    DEFAULT_GRACE_PERIOD,
    DOMAIN,
    MAX_DEBOUNCE,
    MAX_GRACE_PERIOD,
)
from .scene_source import get_scene_targets

_LOGGER = logging.getLogger(__name__)

STEP_DOMAIN = "domain"
FLOW_STATE_DOMAIN = "domain"


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


TIMING_FIELDS: Mapping[Any, Any] = {
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


def _targets(handler: SchemaCommonFlowHandler) -> dict[str, State]:
    """Return the target states of the tracked scene, empty when it is absent."""
    hass = handler.parent_handler.hass
    scene_entity_id = handler.options[CONF_ENTITY_ID]
    return get_scene_targets(hass, scene_entity_id) or {}


def _domains(targets: Mapping[str, State]) -> list[str]:
    """Return the domains whose members have something to compare."""
    return sorted({state.domain for state in targets.values() if comparable(state)})


def _members(targets: Mapping[str, State], domain: str) -> list[State]:
    return [state for state in targets.values() if state.domain == domain]


def _selection_options(targets: Mapping[str, State], domain: str) -> list[str]:
    """Return the names that the user can pick for the domain."""
    names = {
        selection_name(attribute, domain)
        for state in _members(targets, domain)
        for attribute in comparable(state)
    }
    return sorted(names)


def _label(name: str) -> str:
    """Return a readable label for an attribute name.

    Any domain can appear, so the label set is open and cannot live in
    strings.json. The raw name stays visible, because it is also the name in
    the developer tools.
    """
    return name.replace("_", " ").capitalize()


def _select(options: list[str], *, multiple: bool) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                selector.SelectOptionDict(value=name, label=_label(name))
                for name in options
            ],
            multiple=multiple,
            mode=(
                selector.SelectSelectorMode.LIST
                if multiple
                else selector.SelectSelectorMode.DROPDOWN
            ),
        )
    )


async def _init_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Return the timing fields, plus a dropdown when the scene offers a domain."""
    fields: dict[Any, Any] = dict(TIMING_FIELDS)
    domains = _domains(_targets(handler))
    if domains:
        fields[vol.Optional(CONF_CONFIGURE)] = _select(domains, multiple=False)
    return vol.Schema(fields)


async def _remember_domain(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Keep the picked domain for the next step."""
    chosen = user_input.get(CONF_CONFIGURE)
    if chosen is not None:
        handler.flow_state[FLOW_STATE_DOMAIN] = chosen
    return user_input


async def _after_init(options: dict[str, Any]) -> str | None:
    """Continue to the domain step, or end the flow and write the options.

    Popping the key here, rather than in whatever step follows, prevents a
    stuck flow: if the tracked scene disappears, the init schema no longer
    carries this optional key, so nothing else would strip a leftover value
    out of options, and a later submit would keep reading it and routing
    away from a save.
    """
    if options.pop(CONF_CONFIGURE, None) is None:
        return None
    return STEP_DOMAIN


def _stored_rule(handler: SchemaCommonFlowHandler, domain: str) -> Mapping[str, Any]:
    """Return the stored rule of the domain, empty when it is absent or malformed."""
    stored = handler.options.get(domain)
    return stored if isinstance(stored, Mapping) else {}


async def _domain_schema(handler: SchemaCommonFlowHandler) -> vol.Schema | None:
    """Return the checkbox list of the attributes of the picked domain.

    The option list is empty when the domain no longer has anything to
    compare, for example because the tracked scene left the scene platform
    while the dialog was open. A schema of None skips the step, so a stored
    rule is left untouched instead of being overwritten by the only value
    such a step could ever submit: an empty selection. A missing flow_state
    entry (no domain was ever picked, for example a hand-edited entry that
    carries a stale configure value) is treated the same way.
    """
    domain = handler.flow_state.get(FLOW_STATE_DOMAIN)
    options = (
        _selection_options(_targets(handler), domain) if domain is not None else []
    )
    if not options:
        _LOGGER.debug(
            "%s: skipping the domain step, %s has nothing left to compare",
            handler.options.get(CONF_ENTITY_ID),
            domain,
        )
        return None
    return vol.Schema({vol.Required(CONF_COMPARE): _select(options, multiple=True)})


async def _domain_suggestion(handler: SchemaCommonFlowHandler) -> dict[str, Any]:
    """Suggest the stored selection, or every name on a first visit."""
    domain = handler.flow_state[FLOW_STATE_DOMAIN]
    stored = _stored_rule(handler, domain)
    if CONF_COMPARE in stored:
        return {CONF_COMPARE: list(stored[CONF_COMPARE])}
    return {CONF_COMPARE: _selection_options(_targets(handler), domain)}


async def _store_selection(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Write the selection under the domain key, and drop dead tolerances."""
    domain = handler.flow_state[FLOW_STATE_DOMAIN]
    selected = list(user_input[CONF_COMPARE])
    stored = _stored_rule(handler, domain)
    kept = {
        attribute: number
        for attribute, number in stored.items()
        if attribute != CONF_COMPARE and selection_name(attribute, domain) in selected
    }
    return {domain: {CONF_COMPARE: selected, **kept}}


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
    "init": SchemaFlowFormStep(
        _init_schema,
        validate_user_input=_remember_domain,
        next_step=_after_init,
    ),
    STEP_DOMAIN: SchemaFlowFormStep(
        _domain_schema,
        suggested_values=_domain_suggestion,
        validate_user_input=_store_selection,
        next_step="init",
    ),
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
