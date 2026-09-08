# Scene State

A Home Assistant helper that answers one question for a scene: do all entities
in the scene match the states that the scene defines?

Home Assistant scenes are stateless. The scene entity only records when it was
last activated. This helper adds a binary sensor per scene. The sensor is `on`
while every entity in the scene matches its target, and `off` as soon as one of
them drifts away.

## How it works

The helper reads the target states from the scene and compares them with the
current entity states. It compares only the attributes that the scene defines,
and it applies a tolerance to numeric attributes, because devices round values
and report colors in their own representation.

| Domain | Compared attributes and tolerance |
| --- | --- |
| light | brightness within 3, one color representation (kelvin within 50, hue and saturation within 5, xy within 0.02, rgb channels within 5), effect exact |
| cover | position and tilt within 3 |
| fan | percentage within 3, oscillating, direction, and preset mode exact |
| climate | target temperatures within 0.5, preset, fan, and swing mode exact |
| media_player | volume within 0.02, source and sound mode exact |
| humidifier | target humidity within 2, mode exact |
| other | state only |

If the target state is `off` or `closed`, attributes are ignored.

Two timers keep the sensor stable:

- The grace period starts when the scene is activated. Members are compared once
  it ends, so transitions finish first. Default 5 seconds.
- The debounce starts when a member changes. Members are compared once no
  further change arrives within it. Default 1 second.

## Sensor states

| State | Meaning |
| --- | --- |
| `on` | every member matches |
| `off` | at least one member does not match |
| `unknown` | no member mismatches, but at least one is unavailable or missing |
| `unavailable` | the scene entity is not loaded |

Attributes:

- `scene_entity_id`: the tracked scene.
- `mismatched_entities`: the members that do not match, sorted.

## Installation

1. In HACS, open the menu in the top right, then Custom repositories.
2. Add `https://github.com/pszypowicz/scene_state` with category Integration.
3. Install Scene State and restart Home Assistant.

## Configuration

1. Go to Settings, Devices and services, Helpers.
2. Click Create helper and pick Scene State.
3. Select a scene and adjust the grace period and the debounce if needed.

Both timers can be changed later from the helper options.

## Limitations

- Only scenes defined in Home Assistant are supported, from the scene editor or
  from `scenes.yaml`. Scenes that live on a hub, for example Hue or KNX scenes,
  do not expose their targets to Home Assistant.
- Scenes defined in YAML without an `id` have no entity registry entry. A
  rename or removal of such a scene does not update or remove the helper.
- The sensor does not control the scene. Use the scene entity to activate it.

## Development

```bash
uv sync
scripts/lint
scripts/test
scripts/develop
```

`scripts/develop` starts Home Assistant from `config/` with the demo
integration and a few sample scenes, and links this component into it.
