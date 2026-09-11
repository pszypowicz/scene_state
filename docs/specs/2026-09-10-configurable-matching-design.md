# Configurable matching design, release 0.1.0

## Goal

Release 0.0.1 holds the matching rules in the code. A per-domain table names the
attributes that count, and a tolerance number accompanies each one. Every user
gets the same rules, and nobody can change them.

This release moves both decisions into the config entry. The scene supplies the
attribute list. The user picks which of those attributes count, and sets a
tolerance for any numeric one. No tolerance number ships in the code.

## Decisions

| Item                               | Decision                                             |
| ---------------------------------- | ---------------------------------------------------- |
| Comparison default                 | exact, for every attribute the scene stores          |
| Tolerance defaults in code         | none                                                 |
| Per-domain attribute lists in code | none, the scene supplies them                        |
| Scope of an override               | per config entry, per domain                         |
| Tolerance scale                    | the scale of the attribute itself, no conversion     |
| Stored selection                   | positive, the attributes to compare                  |
| Tolerance suggestion               | measured from the current states when the form opens |
| Flow shape                         | three steps, a domain dropdown on `init`             |
| Supported domains                  | any domain present in the scene                      |
| Entry migration                    | none, an absent key means compare everything exactly |
| Version                            | 0.1.0                                                |

## Breaking change

Release 0.0.1 applied built-in tolerances to fifteen attributes. After this
change the comparison is exact until the user sets a tolerance. Existing entries
keep their options and change behavior on upgrade. A scene that reported `on`
can report `off` after the upgrade.

The release notes and the README must state this plainly, together with the
repair: open the helper options, pick the domain, and accept the suggested
tolerance.

## Scope

In scope:

- Delete `ATTRIBUTE_RULES`, `COLOR_COMPARATORS`, and every tolerance number.
- Delete `_clamp_kelvin` and the two constants it reads.
- A generic metadata filter over the attributes of a desired state.
- A `compare` list and tolerance values per domain in the entry options.
- A three-step options flow that reads the tracked scene.
- A measured tolerance suggestion per numeric attribute.
- Support for any domain that appears in the scene.

Out of scope:

- Per-entity overrides. The scope is the domain.
- A tolerance for an attribute that the scene does not store.
- A separate tolerance per color channel. One number covers every channel.
- A target limit from `min_<attribute>` and `max_<attribute>`.
- Any tolerance or override on the state string.
- Mismatch detail on the sensor. `mismatched_entities` keeps its current
  content.

## Behavior

### Matching rules

These rules replace the Matching rules section of the 0.0.1 design.

1. The state string must equal the desired state string.
2. If the desired state is `off` or `closed`, attributes are ignored.
3. The comparable attributes of a desired state are the attributes it stores,
   minus the metadata filter, minus the color representations that the color
   rule does not select.
4. A desired attribute value of `None` is ignored.
5. A desired attribute that the current state does not report is a mismatch.
6. The comparison set for a domain is the stored `compare` list when the entry
   holds one. Otherwise it is every comparable attribute of that desired state.
7. An attribute with a stored tolerance compares numerically. Every other
   attribute compares exactly.
8. Numeric tolerances are inclusive. A difference equal to the tolerance is a
   match.
9. A stored `compare` list of zero length compares the state string only.
10. A stored tolerance against a value that is not numeric falls back to an
    exact equality check.

### Metadata filter

The `scene.create` service stores the full live attribute set of a member, so a
snapshot scene carries attributes that describe the entity rather than its
state, some as presentation and some as capability. The filter drops them
before the user sees them.

| Rule        | Values                                                                                                                                                          |
| ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Exact names | `assumed_state`, `attribution`, `device_class`, `editable`, `entity_id`, `entity_picture`, `friendly_name`, `icon`, `supported_features`, `unit_of_measurement` |
| Prefixes    | `supported_`, `available_`, `min_`, `max_`                                                                                                                      |
| Suffixes    | `_list`, `_modes`                                                                                                                                               |

The exact names come from the constants in `homeassistant.const`, not from
string literals. The prefixes and the suffixes follow Home Assistant naming
conventions and name no platform. The `_modes` suffix drops `hvac_modes` and
keeps `fan_mode`. The prefix and suffix rules, not the exact names, are what
catch the capability lists, such as `supported_color_modes` and `effect_list`.

The filter removes capability metadata only. A media player snapshot also
carries `media_position` and `media_title`, which change on every track. Those
reach the checkbox list, and the user clears them. This division is deliberate.
An incomplete filter leaves an attribute visible and fixable. A filter that
guesses at volatile platform attributes would hide a comparison that somebody
wants.

### Light color

A light reports every color representation at once, and all of them derive from
one value. Comparison of all of them fails on any light that converts through
its own gamut, so one representation carries the comparison.

1. If the desired state has `color_mode`, that mode selects the representation.
   `color_temp` selects `color_temp_kelvin`. `hs` selects `hs_color`. `xy`
   selects `xy_color`. `rgb`, `rgbw`, and `rgbww` select the attribute with the
   same name. `white`, `onoff`, and `brightness` select no color attribute.
2. If the desired state has no `color_mode`, the first attribute present from
   this list selects the representation: `color_temp_kelvin`, `hs_color`,
   `rgb_color`, `xy_color`, `rgbw_color`, `rgbww_color`.
3. The selected attribute is the only color attribute in the comparable set. The
   other representations are excluded even when the scene stores them. The
   current `color_mode` is not compared.
4. The user selects color under one name, `color`. That name covers whichever
   representation rule 1 or rule 2 selects, for every member of the domain.
5. A tolerance is stored under the concrete attribute name, because the scale
   belongs to the representation. `hs_color` and `xy_color` do not share a
   scale.
6. A sequence compares element by element, with one tolerance for every
   element. Sequences of different length mismatch.

The desired kelvin value is no longer limited to the range that the current
state reports. Release 0.0.1 did that, and it hid a hardware difference behind
an invisible rule. A light that cannot reach the requested value now needs a
tolerance, and the flow measures the gap and suggests it.

### Tolerance suggestion

The tolerances step measures the live difference for every field it renders.

1. For each member of the domain, read the desired value and the current value.
2. Skip a member that is missing, `unavailable`, `unknown`, or whose current
   state string differs from the desired one.
3. For a number, the difference is the absolute difference. For a sequence, it
   is the largest absolute difference across the elements.
4. The measurement for an attribute is the largest difference across the
   members.
5. The suggested value of a field is the stored tolerance when the entry holds
   one. Otherwise it is the measurement.
6. The step description lists the measurement of every attribute the step
   renders a field for, whether stored or not.

Rule 5 keeps a second visit from overwriting a value that the user chose. Rule 6
keeps the current measurement visible on that second visit.

The comparison uses `difference <= tolerance + FLOAT_MARGIN`, so a tolerance
equal to the measurement makes a present, reporting member match. It does not
help a member that is unavailable, since the tracker never calls the
comparator for it, nor a loaded member that does not report the attribute at
all, since a missing attribute is a mismatch before any tolerance applies.

## Options storage

```json
{
  "entity_id": "scene.movie_night",
  "grace_period": 5.0,
  "debounce": 1.0,
  "light": {
    "compare": ["brightness", "color"],
    "brightness": 2,
    "color_temp_kelvin": 300
  }
}
```

| Key                                     | Meaning                                                           |
| --------------------------------------- | ----------------------------------------------------------------- |
| `entity_id`, `grace_period`, `debounce` | reserved, as in 0.0.1                                             |
| any other top level key                 | a domain name, with a mapping as its value                        |
| `compare` inside a domain               | the attribute names that count, with `color` for the light family |
| any other key inside a domain           | a tolerance, under the concrete attribute name                    |

A domain key stays absent until the user submits that domain step. An absent key
means compare every comparable attribute exactly, so an entry from 0.0.1 needs
no migration. The config entry version stays at 1.1.

`from_options` treats a top level key as a domain only when the key is not
reserved and the value is a mapping. An unknown key of another type is ignored.

## Options flow

The flow has three steps. A menu was the first choice and it does not work here.
A menu row must name a step that the handler registered at construction time,
and the domains come from the scene at run time. A select field holds an
arbitrary value, so `init` is a form.

### `init`

| Field          | Selector                                       | Presence            |
| -------------- | ---------------------------------------------- | ------------------- |
| `grace_period` | number, 0 to 600, step 0.5, unit seconds       | required, default 5 |
| `debounce`     | number, 0 to 60, step 0.5, unit seconds        | required, default 1 |
| `configure`    | select, single, the domains found in the scene | optional            |

The schema is a callable. It reads the member entity IDs through
`get_scene_targets` and offers their domains, sorted. If the scene is not loaded
the list is empty, and the `configure` field is left out of the schema.

`validate_user_input` writes the chosen domain into `flow_state`, and returns the
input unchanged. `configure` therefore reaches the options, because `next_step`
receives the options and nothing else.

`next_step` is a callable, `_after_init`. It pops `configure` from the options
right away, then returns `"domain"` when the key held a value, and `None`
otherwise. `None` writes the options to the entry and closes the dialog.
Popping the key in this routing callable, rather than in the `domain` step,
keeps the flow from getting stuck when the tracked scene disappears and the
`domain` step skips itself.

So a submit with an empty dropdown saves and closes. There is no separate save
step.

### `domain`

| Field     | Selector                    |
| --------- | --------------------------- |
| `compare` | select, multiple, list mode |

The options are the comparable attribute names of that domain, as the union over
its members, with `color` in place of any selected color representation. The
labels come from `strings.json` through a `translation_key`. Any domain can
appear, so the label set is open. The implementation must confirm that the
frontend shows the raw attribute name when a label is absent, and must build the
labels in code if it does not.

`suggested_values` returns the stored `compare` list when the entry holds one,
and every option otherwise. So a first visit arrives with everything checked,
which is the exact-match default made visible.

`validate_user_input` does two things. It keeps the stored tolerances of the
attributes that stay selected, and drops the rest. It returns a mapping under
the domain key. `configure` never reaches this step; the `init` step's own
routing callable, `_after_init`, already popped it.

A tolerance survives when `selection_name` maps its concrete attribute to a name
in the new `compare` list. So a cleared `color` box drops the tolerance of every
color representation.

`next_step` is `"tolerances"`.

### `tolerances`

| Field                     | Selector                                |
| ------------------------- | --------------------------------------- |
| one per numeric attribute | number, minimum 0, step `any`, box mode |

The field set holds every selected attribute whose desired value is a number or
a sequence of numbers. For `color` it holds one field per concrete
representation that the members use, so a scene of kelvin lights shows one
field.

No field carries a maximum or a unit. The scale belongs to the attribute, and
the form has no table to read a bound from. The step is dynamic through
`schema`, `suggested_values`, and `description_placeholders`.

The schema callable returns `None` when the field set is empty, and the flow
then skips the step. A user who selects `effect` alone returns straight to
`init`.

`validate_user_input` merges the numbers into the domain mapping. `next_step` is
`"init"`.

### Flow diagram

```text
init  ── empty dropdown ──> write options, close
  │
  └── domain picked ──> domain ──> tolerances ──> init
                                │
                                └── no numeric field ──> init
```

## Architecture

One new module. The rest keep their current responsibilities.

| Module             | Responsibility                                                                   | Depends on                              |
| ------------------ | -------------------------------------------------------------------------------- | --------------------------------------- |
| `attributes.py`    | which attributes of a desired state are comparable, and the measured differences | `homeassistant.const`, `State`          |
| `matching.py`      | comparators, `MatchProfile`, `match_state`                                       | `attributes`, `State`                   |
| `config_flow.py`   | the three steps                                                                  | `attributes`, `scene_source`, selectors |
| `tracker.py`       | holds a profile and passes it to `match_state`                                   | as today                                |
| `binary_sensor.py` | builds the profile from the entry options                                        | as today                                |
| `const.py`         | the new option keys                                                              | `homeassistant.const`                   |

`matching.py` keeps the comparison and loses the data. `attributes.py` holds the
one view of a desired state that both the comparison and the form need, so the
two cannot drift apart.

### `attributes.py`

```python
COLOR_NAME: Final = "color"

def select_color_attribute(desired: Mapping[str, Any]) -> str | None: ...

def comparable(desired: State) -> tuple[str, ...]:
    """Return the concrete attribute names that take part in the comparison."""

def selection_name(attribute: str, domain: str) -> str:
    """Return the name under which the user selects this attribute."""

def numeric_differences(desired: State, current: State) -> dict[str, float]:
    """Return the absolute difference per comparable numeric attribute."""
```

`selection_name` returns `COLOR_NAME` for a color representation of a light, and
the attribute itself otherwise. The comparison and the form both route through
it, so one function defines the mapping between a stored selection and a
concrete attribute.

`numeric_differences` keys its result by the concrete attribute name. A value
that is not numeric is left out.

### `matching.py`

```python
@dataclass(frozen=True, slots=True)
class MatchProfile:
    """The comparison rules of one config entry."""

    compare: Mapping[str, frozenset[str]]
    tolerances: Mapping[str, Mapping[str, float]]

    @classmethod
    def from_options(cls, options: Mapping[str, Any]) -> MatchProfile: ...

    def compares(self, domain: str, attribute: str) -> bool: ...

    def tolerance(self, domain: str, attribute: str) -> float | None: ...


@dataclass(frozen=True, slots=True)
class MatchResult:
    matches: bool
    reason: str | None = None


def match_state(
    desired: State, current: State, profile: MatchProfile
) -> MatchResult: ...
```

`compares` returns `True` for every comparable attribute when the profile holds
no selection for that domain. The profile records the absence of a selection,
and it does not fill one in, because an absent domain and an empty `compare`
list mean different things.

`profile` is a required argument. A default value would let a missing call site
fall back to permissive behavior without a failure.

`_sequence_within` takes one tolerance instead of a tuple, and it compares the
length of the desired value with the length of the current value. The length no
longer comes from a table.

### `tracker.py`

`SceneTracker.__init__` takes `profile: MatchProfile` after `debounce`, stores
it, and passes it to every `match_state` call. Nothing else changes. The entry
reloads on an options change through `options_flow_reloads`, so the tracker
never replaces its profile in place.

### `binary_sensor.py`

`SceneStateBinarySensor.__init__` builds the profile with
`MatchProfile.from_options(entry.options)` and passes it to the tracker.

### `const.py`

```python
CONF_COMPARE: Final = "compare"
CONF_CONFIGURE: Final = "configure"
RESERVED_OPTION_KEYS: Final = frozenset(
    {CONF_ENTITY_ID, CONF_GRACE_PERIOD, CONF_DEBOUNCE, CONF_CONFIGURE}
)
```

### Error handling

- The flow never raises when the scene is missing or unloaded. The `configure`
  field is left out, and the timing fields still work.
- A member that is missing, `unavailable`, `unknown`, or whose current state
  string differs from the desired one, is skipped during measurement. It does
  not make the flow fail.
- A malformed desired value, for example a color sequence of the wrong length,
  is a mismatch with a reason.
- `configure` never reaches the entry. A test asserts it.

## Testing

- `tests/test_attributes.py`, new. The metadata filter drops each exact name,
  each prefix, and each suffix. A snapshot style state with the full light
  attribute set yields only `brightness` and the selected representation.
  `selection_name` maps every color representation to `color`, and leaves other
  attributes alone. `numeric_differences` handles a number, a sequence, a
  missing current value, and a value that is not numeric.
- `tests/test_matching.py`. An empty profile compares every stored attribute
  exactly. A difference of one on `brightness` is a mismatch without a
  tolerance, and a match with a tolerance of one. A `compare` list that omits an
  attribute ignores it. An empty `compare` list compares the state only. A
  `compare` list holding `color` compares the selected representation. A stored
  tolerance on a string value falls back to an exact equality check, matching
  equal strings and mismatching unequal ones. The kelvin tests from 0.0.1 lose
  the clamp and gain a tolerance.
- `tests/test_config_flow.py`. The `init` dropdown lists the domains of the
  scene and nothing else. An unloaded scene leaves the dropdown out. A submit
  with an empty dropdown writes the options and closes. A domain step arrives
  with every attribute selected. A second visit arrives with the stored
  selection. The tolerances step renders one field per numeric attribute, and
  suggests the measured difference on a first visit and the stored value after
  that. A selection without a numeric attribute skips the tolerances step. An
  empty selection stores as an empty list and does not fall back to the default.
  The `configure` key never appears in `entry.options`.
- `tests/test_tracker.py`. The tracker passes its profile to `match_state`. The
  same member state gives a different status under two profiles.
- `tests/test_binary_sensor.py`. An options change reloads the entry and the new
  profile takes effect. An entry whose options hold no domain key compares
  exactly.

## Documentation

- `README.md`. The How it works section loses the per-domain tolerance table. It
  states that the comparison is exact, that the scene supplies the attribute
  list, and how to set a tolerance. The Configuration section gains the three
  steps.
- `strings.json` and `translations/en.json`. Three steps, the attribute labels
  for the `compare` selector, and the measurement placeholder on the tolerances
  step.
- `manifest.json`. The version becomes 0.1.0.
- The release notes carry the breaking-change note from the section above.

## Follow-ups

- Mismatch detail on the sensor. `match_state` already computes the failing
  attribute and both values, and today only the debug log sees them. A
  structured attribute would let a user find the right tolerance without the
  log.
- An opt-in target limit. A per-domain switch that limits the desired value to
  the range that the entity publishes as `min_<attribute>` and
  `max_<attribute>`. It carries no attribute names, it covers
  `color_temp_kelvin` and `humidity`, and it misses climate, because core names
  that range `min_temp` and `max_temp`.
- Per-entity overrides, if one misbehaving member in a domain proves common.
