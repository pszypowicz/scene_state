"""Config flow for the Scene State integration."""

from collections.abc import Mapping, Sequence
import logging
from typing import Any, override

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    wrapped_entity_config_entry_title,
)
import voluptuous as vol

from .attributes import comparable, is_numeric, numeric_differences, selection_name
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
    UNKNOWN_STATES,
)
from .matching import STATES_WITHOUT_ATTRIBUTES
from .scene_source import get_scene_targets

_LOGGER = logging.getLogger(__name__)

STEP_DOMAIN = "domain"
STEP_TOLERANCES = "tolerances"
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


def _tolerance_attributes(
    targets: Mapping[str, State], domain: str, selected: Sequence[str]
) -> list[str]:
    """Return the concrete numeric attributes that the selection covers."""
    names = {
        attribute
        for state in _members(targets, domain)
        for attribute in comparable(state)
        if selection_name(attribute, domain) in selected
        and is_numeric(state.attributes[attribute])
    }
    return sorted(names)


def _measurements(
    hass: HomeAssistant, targets: Mapping[str, State], domain: str
) -> dict[str, float]:
    """Return the largest live difference per attribute of the domain."""
    largest: dict[str, float] = {}
    for entity_id, desired in targets.items():
        if desired.domain != domain:
            continue
        current = hass.states.get(entity_id)
        if current is None or current.state in UNKNOWN_STATES:
            continue
        # match_state rejects on the state string before it reads any
        # attribute, and it matches a desired state of off or closed without
        # reading one at all, so an attribute difference is meaningless while
        # the states differ, and irrelevant when the desired state makes
        # attributes moot; neither member could ever benefit from a
        # tolerance here.
        if current.state != desired.state:
            continue
        if desired.state in STATES_WITHOUT_ATTRIBUTES:
            continue
        for attribute, difference in numeric_differences(desired, current).items():
            largest[attribute] = max(largest.get(attribute, 0.0), difference)
    return largest


def _selected(handler: SchemaCommonFlowHandler) -> tuple[str, list[str]] | None:
    """Return the picked domain and its stored selection, None when there is none.

    No domain is picked when flow_state never received one, for example a
    hand-edited entry that carries a stale configure value. The domain step
    also skips itself when its scene has nothing left to compare, which can
    leave the stored rule absent, malformed, or missing its compare list by
    the time this step runs.
    """
    domain = handler.flow_state.get(FLOW_STATE_DOMAIN)
    if domain is None:
        return None
    stored = _stored_rule(handler, domain)
    selected = stored.get(CONF_COMPARE)
    if not isinstance(selected, list | tuple):
        return None
    return domain, list(selected)


async def _tolerances_schema(
    handler: SchemaCommonFlowHandler,
) -> vol.Schema | None:
    """Return one number field per numeric attribute, or None for none."""
    picked = _selected(handler)
    if picked is None:
        return None
    domain, selected = picked
    attributes = _tolerance_attributes(_targets(handler), domain, selected)
    if not attributes:
        return None
    return vol.Schema(
        {
            vol.Required(attribute): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, step="any", mode=selector.NumberSelectorMode.BOX
                )
            )
            for attribute in attributes
        }
    )


async def _tolerance_suggestion(
    handler: SchemaCommonFlowHandler,
) -> dict[str, Any]:
    """Suggest the stored tolerance, or the measured difference.

    The None branch covers a domain rule that is absent, malformed, or
    missing its compare list, the runtime states `_selected` describes.
    """
    picked = _selected(handler)
    if picked is None:
        return {}
    domain, selected = picked
    targets = _targets(handler)
    stored = _stored_rule(handler, domain)
    measured = _measurements(handler.parent_handler.hass, targets, domain)
    return {
        attribute: stored.get(attribute, measured.get(attribute, 0.0))
        for attribute in _tolerance_attributes(targets, domain, selected)
    }


async def _tolerance_description(
    handler: SchemaCommonFlowHandler,
) -> dict[str, str]:
    """Report the live difference per attribute that the step renders a field for."""
    picked = _selected(handler)
    if picked is None:
        return {"measured": "none"}
    domain, selected = picked
    targets = _targets(handler)
    fields = _tolerance_attributes(targets, domain, selected)
    measured = _measurements(handler.parent_handler.hass, targets, domain)
    shown = {
        attribute: measured[attribute] for attribute in fields if attribute in measured
    }
    if not shown:
        return {"measured": "none"}
    return {
        "measured": ", ".join(
            f"{attribute} {difference:g}"
            for attribute, difference in sorted(shown.items())
        )
    }


async def _store_tolerances(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Merge the numbers into the mapping of the domain."""
    domain = handler.flow_state[FLOW_STATE_DOMAIN]
    stored = dict(handler.options[domain])
    stored.update({name: float(number) for name, number in user_input.items()})
    return {domain: stored}


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
        next_step=STEP_TOLERANCES,
    ),
    STEP_TOLERANCES: SchemaFlowFormStep(
        _tolerances_schema,
        suggested_values=_tolerance_suggestion,
        validate_user_input=_store_tolerances,
        description_placeholders=_tolerance_description,
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
