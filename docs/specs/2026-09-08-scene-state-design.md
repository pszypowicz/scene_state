# Scene State design, release 0.0.1

## Goal

Scene State is a Home Assistant helper integration. For a scene, it answers one
question: do all entities in the scene match the states that the scene defines?
The answer is a `binary_sensor` entity per tracked scene.

Home Assistant scenes are stateless. The scene entity state is the timestamp of
the last activation. Nothing in core reports whether the scene is still in
effect. Home Assistant had this feature in 2015 and removed it, because exact
comparison of entity attributes fails on transitions, rounding, and color
conversion. This project applies per-attribute tolerances, a grace period after
activation, and a debounce on member updates, so that the answer is stable.

## Decisions

| Item | Decision |
| --- | --- |
| Repository | `pszypowicz/scene_state`, public, default branch `main` |
| Integration domain | `scene_state` |
| License | MIT |
| Entity per scene | one `binary_sensor` |
| Scene source | target states from the built-in `homeassistant` scene platform |
| Home Assistant version for development | 2026.9.1 |
| Minimum Home Assistant version | 2026.9.0 |

## Scope of 0.0.1

In scope:

- A config entry per scene, created from the Helpers page.
- A `binary_sensor` per config entry with the states `on`, `off`, `unknown`, and
  `unavailable`.
- Two attributes on the sensor: the scene entity ID and the list of mismatched
  entity IDs.
- An options flow for the grace period and the debounce time.
- Scene rename handling and scene removal handling through the core helper API.

Out of scope:

- Scenes from other integrations, for example Hue, KNX, or Qbus. Core does not
  know their target states.
- An off scene, restore on deactivate, or any control entity such as a switch.
- Per-entry tolerance overrides.
- Devices. The sensor links to no device.

## Behavior

### Sensor state

| Condition | Sensor state |
| --- | --- |
| The scene entity is not loaded in the built-in scene platform | `unavailable` |
| Any member mismatches | `off` |
| No member mismatches, and any member is missing, `unavailable`, or `unknown` | `unknown` |
| All members match | `on` |

A mismatch wins over an unknown member. This keeps the sensor deterministic when
one member is offline and another one changed.

### Attributes

| Attribute | Value |
| --- | --- |
| `scene_entity_id` | the tracked scene entity ID |
| `mismatched_entities` | sorted list of member entity IDs that do not match, empty when the sensor is `on` or `unknown` |

### Timing

- Grace period, default 5 seconds, range 0 to 600 seconds. It starts when the
  scene entity state changes to a new timestamp. A change from no state to a
  timestamp counts as well, for example when the scene entity appears after a
  reload. Member events during the grace period do not start an evaluation. One
  evaluation runs when the grace period ends.
- Debounce, default 1 second, range 0 to 60 seconds. A member state change
  starts the debounce timer. A new member event restarts it. One evaluation runs
  when the timer expires. A value of 0 evaluates on every event.
- A scene activation cancels a pending debounce timer.
- The first evaluation runs when the config entry loads, without timers.

### Matching rules

Every evaluation reads the target states again from the scene platform. A scene
reload therefore needs no special handling.

Rules that apply to every domain:

1. The state string must be equal to the desired state string.
2. If the desired state is `off` or `closed`, attributes are ignored.
3. Only attributes that the scene defines are compared, and only attributes from
   the per-domain list below. The scene editor stores every attribute of an
   entity, so all other attributes are ignored.
4. A desired attribute value of `None` is ignored.
5. A desired attribute that the current state does not report is a mismatch.
6. Numeric tolerances are inclusive. A difference equal to the tolerance is a
   match.

Per-domain attribute lists:

| Domain | Attribute | Rule |
| --- | --- | --- |
| `light` | `brightness` | within 3 on the 0 to 255 scale |
| `light` | color | one representation, see below |
| `light` | `effect` | exact |
| `cover` | `current_position` | within 3 |
| `cover` | `current_tilt_position` | within 3 |
| `fan` | `percentage` | within 3 |
| `fan` | `oscillating` | exact |
| `fan` | `direction` | exact |
| `fan` | `preset_mode` | exact |
| `climate` | `temperature` | within 0.5 |
| `climate` | `target_temp_high` | within 0.5 |
| `climate` | `target_temp_low` | within 0.5 |
| `climate` | `preset_mode` | exact |
| `climate` | `fan_mode` | exact |
| `climate` | `swing_mode` | exact |
| `media_player` | `volume_level` | within 0.02 |
| `media_player` | `source` | exact |
| `media_player` | `sound_mode` | exact |
| `humidifier` | `humidity` | within 2 |
| `humidifier` | `mode` | exact |
| any other domain | none | state only |

Light color rules:

1. If the desired state has `color_mode`, that mode selects the representation.
   `color_temp` selects `color_temp_kelvin`. `hs` selects `hs_color`. `xy`
   selects `xy_color`. `rgb`, `rgbw`, and `rgbww` select the attribute with the
   same name. `white`, `onoff`, and `brightness` select no color attribute.
2. If the desired state has no `color_mode`, the first attribute present from
   this list selects the representation: `color_temp_kelvin`, `hs_color`,
   `rgb_color`, `xy_color`, `rgbw_color`, `rgbww_color`.
3. The current state must have the selected attribute. If it is absent, the
   light mismatches. The current `color_mode` is not compared. Lights report
   derived values for other representations, and the selected attribute carries
   the comparison.
4. Tolerances. `color_temp_kelvin` within 50, after the desired value is clamped
   to the `min_color_temp_kelvin` and `max_color_temp_kelvin` of the current
   state, when present. `hs_color` hue within 5 and saturation within 5.
   `xy_color` each coordinate within 0.02. `rgb_color`, `rgbw_color`, and
   `rgbww_color` each channel within 5.
5. Lists of different length mismatch.

## Architecture

All code lives in `custom_components/scene_state/`.

| Module | Responsibility | Depends on |
| --- | --- | --- |
| `const.py` | domain, option keys, defaults, ranges | nothing |
| `scene_source.py` | read target states of a scene from the built-in scene platform | core internals, see below |
| `matching.py` | pure comparison of a desired `State` and a current `State` | `homeassistant.core.State` only |
| `tracker.py` | subscriptions, timers, evaluation, aggregate result | `scene_source`, `matching`, event helpers |
| `binary_sensor.py` | the entity, owns the tracker, maps its status to a state | `tracker` |
| `config_flow.py` | schema-based config and options flow | selectors |
| `__init__.py` | entry setup, unload, source entity changes | `tracker`, helper integration API |

### `scene_source.py`

One function:

```python
def get_scene_targets(hass: HomeAssistant, scene_entity_id: str) -> dict[str, State] | None
```

It reads the entity platform stored under the `homeassistant_scene` key in
`hass.data`, looks up the scene entity, and returns a copy of
`scene_config.states`. It returns `None` when the platform is not set up or the
scene entity is not present. Core reads the same data for its own
`entities_in_scene` helper. This module is the only place that touches this
data. A later core pull request adds a public accessor, and then this module
calls it.

The platform data key is assigned by the first `scene:` platform load. A
`scene:` block with its own `scan_interval` or `entity_namespace` creates a
separate platform instance, and its scenes are not visible to the adapter.

### `matching.py`

```python
@dataclass(frozen=True, slots=True)
class MatchResult:
    matches: bool
    reason: str | None


def match_state(desired: State, current: State) -> MatchResult
```

`reason` is a short text for the debug log, for example
`brightness: wanted 200, got 120`. The module holds the per-domain attribute
table and the light color rules. It imports nothing from Home Assistant other
than `State`. Attribute names are literals in the module.

### `tracker.py`

```python
class SceneStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNKNOWN = "unknown"
    SCENE_MISSING = "scene_missing"


class SceneTracker:
    def __init__(
        self,
        hass: HomeAssistant,
        scene_entity_id: str,
        grace_period: float,
        debounce: float,
        on_update: Callable[[], None],
    ) -> None: ...

    status: SceneStatus
    mismatched: list[str]

    @callback
    def async_start(self) -> None: ...

    @callback
    def async_stop(self) -> None: ...
```

`async_start` runs one evaluation, subscribes to the member entity IDs with
`async_track_state_change_event`, and subscribes to the scene entity with the
same helper. When an evaluation finds a different member set, for example after
a scene reload, the tracker replaces the member subscription. `async_stop`
cancels timers and removes subscriptions. Timers use `async_call_later`. The
tracker calls `on_update` after every evaluation, and the entity writes its
state.

Evaluation:

1. Read the targets. If `None`, set `SCENE_MISSING` and return.
2. For each member, get the current state. If absent, `unavailable`, or
   `unknown`, mark the member unknown. Otherwise call `match_state` and record a
   mismatch when it fails, with the reason at debug level.
3. Aggregate with the table in the Behavior section.

### `binary_sensor.py`

- `_attr_should_poll = False`, `_attr_has_entity_name = True`, and the name is
  the config entry title, which is the scene friendly name at creation time.
- The entity creates and owns the tracker. It starts the tracker in
  `async_added_to_hass` and stops it on removal.
- `unique_id` is the config entry ID.
- `available` is `False` when the status is `SCENE_MISSING`.
- `is_on` is `True` for `ACTIVE`, `False` for `INACTIVE`, and `None` for
  `UNKNOWN`.
- No `device_class`.

### `config_flow.py`

The flow uses `SchemaConfigFlowHandler` with one `user` step and one `init`
options step, the same pattern as the `threshold` helper in core. All values
are stored in the entry options.

| Option | Selector | Default |
| --- | --- | --- |
| `entity_id` | entity selector, domain `scene`, integration `homeassistant` | required |
| `grace_period` | number selector, 0 to 600, step 0.5, unit seconds | 5 |
| `debounce` | number selector, 0 to 60, step 0.5, unit seconds | 1 |

The entry title is the friendly name of the scene at creation time. The flow
aborts with `already_configured` when an entry for the same scene entity ID
exists.

### `__init__.py`

- `async_setup_entry` registers `async_handle_source_entity_changes` from
  `homeassistant.helpers.helper_integration`, so that a rename of the scene
  entity updates the option, and a removal of the scene entity removes the
  config entry. It then forwards the `binary_sensor` platform.
- The schema flow handler sets `options_flow_reloads`, so an options change
  reloads the entry without a separate update listener.
- `async_unload_entry` unloads the platform, which stops the tracker.

### Error handling

- No evaluation raises. Missing data maps to `SCENE_MISSING` or to an unknown
  member.
- Every mismatch reason goes to the debug log with the scene entity ID and the
  member entity ID.
- A malformed desired attribute, for example a color list of the wrong length,
  is a mismatch with a reason, not an exception.

## Repository layout

```text
.github/workflows/ci.yml
config/configuration.yaml
config/scenes.yaml
custom_components/scene_state/
docs/specs/
scripts/develop
scripts/lint
scripts/test
tests/
hacs.json
pyproject.toml
README.md
LICENSE
```

- `hacs.json` sets the name, `render_readme`, and the minimum Home Assistant
  version.
- `manifest.json` sets `integration_type` to `helper`, `iot_class` to
  `calculated`, `config_flow` to `true`, and `version` to `0.0.1`.
- `strings.json` and `translations/en.json` hold the flow strings.
- `README.md` describes what the helper does, the matching rules in short, the
  installation through HACS as a custom repository, and the options.

## Development environment

- `pyproject.toml` declares `requires-python = ">=3.14.2"` and a `dev`
  dependency group with `homeassistant==2026.9.1`,
  `pytest-homeassistant-custom-component==0.13.364`, `ruff`, and `mypy`.
  `uv sync` creates the virtual environment. The lock file is committed.
- Ruff and mypy configuration follows Home Assistant core. Mypy runs in strict
  mode on `custom_components/scene_state`.
- `config/configuration.yaml` enables `default_config`, `demo`, and debug
  logging for `custom_components.scene_state`.
- `config/scenes.yaml` defines sample scenes over demo entities, at minimum:
  a light scene with brightness and color temperature, a light scene with an
  hs color, a cover scene with a position, a climate scene with a target
  temperature, and a media player scene with a volume level.
- `scripts/develop` links `custom_components/scene_state` into
  `config/custom_components/` and runs `hass -c config --debug`. The link and
  the runtime files under `config/` are ignored by git, except
  `configuration.yaml` and `scenes.yaml`.
- `scripts/lint` runs ruff format check, ruff check, and mypy. `scripts/test`
  runs pytest.

## Testing

Tests use `pytest-homeassistant-custom-component`.

- `tests/test_matching.py`: a parametrized table per domain. Cases: state
  mismatch, off ignores attributes, brightness inside and outside tolerance,
  each color representation inside and outside tolerance, kelvin clamp, a
  scene without `color_mode`, a current state without the selected color
  attribute, lists of different length, cover position, climate target
  temperature, media player volume, a domain without rules, and unknown
  attributes ignored.
- `tests/test_tracker.py`: debounce restarts on a new event, grace period
  absorbs member events, activation cancels a pending debounce, a member
  set change after scene reload replaces the subscription, `async_stop`
  cancels timers. Time moves with `async_fire_time_changed`.
- `tests/test_binary_sensor.py`: sensor `on`, `off`, and `unknown` cases,
  unavailable when the scene is missing, mismatched attribute content, and a
  reload after an options change. Scenes are created through the real
  `homeassistant` scene platform in the test instance.
- `tests/test_config_flow.py`: create an entry, abort on duplicate, options
  flow updates and reload.
- `tests/test_init.py`: setup and unload, scene rename updates the option,
  scene removal removes the entry.

## Continuous integration

One workflow on push to `main` and on pull requests, with these jobs:

- hassfest through `home-assistant/actions/hassfest`
- HACS validation through `hacs/action` with category `integration`
- ruff format check and ruff check
- mypy
- pytest

## Release process

- Commits land on `main` directly until the first tag.
- The manifest version is `0.0.1`. The tag `v0.0.1` is created when the helper
  works on the development server with the demo scenes and CI is green.

## Follow-ups after 0.0.1

- Core pull request: a public function in
  `homeassistant.components.homeassistant.scene` that returns the target states
  of a scene, next to `entities_in_scene`.
- A switch entity with an optional off scene, once the matching proves stable.
- Per-entry tolerance overrides, if real scenes need them.
