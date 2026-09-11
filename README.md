# Scene State

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/pszypowicz/scene_state)](https://github.com/pszypowicz/scene_state/releases)
[![CI](https://github.com/pszypowicz/scene_state/actions/workflows/ci.yml/badge.svg)](https://github.com/pszypowicz/scene_state/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/pszypowicz/scene_state)](LICENSE)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Maintainer](https://img.shields.io/badge/maintainer-%40pszypowicz-blue.svg)](https://github.com/pszypowicz)

A Home Assistant helper that answers one question for a scene: do all entities
in the scene match the states that the scene defines?

Home Assistant scenes are stateless. The scene entity only records when it was
last activated. This helper adds a binary sensor per scene. The sensor is `on`
while every entity in the scene matches its target, and `off` as soon as one of
them drifts away.

## How it works

The helper reads the target states from the scene and compares them with the
current entity states. It compares only the attributes that the scene stores,
and it compares them exactly. A scene is set when every member matches
perfectly.

Devices do not always report back the value that the scene asked for. A light
converts a color through its own gamut, an integration that stores brightness as
a percent returns 101 for 100, and a time based cover estimates its position. For
each of those, set a tolerance in the helper options.

Two kinds of attribute never take part. Capability attributes, such as
`supported_features` and `effect_list`, describe what an entity can do. For a
light, only one color representation counts, because a light reports all of them
at once and all of them derive from one value.

If the target state is `off` or `closed`, attributes are ignored.

Two timers keep the sensor stable:

- The grace period starts when the scene is activated. Members are compared once
  it ends, so transitions finish first. Default 5 seconds.
- The debounce starts when a member changes. Members are compared once no
  further change arrives within it. Default 1 second.

### When the sensor reports off

Three different causes make the sensor report `off`, and each one needs its own
repair.

Clear the attribute when you do not care about it. This is also the only repair
for an attribute that drifts without limit, such as `media_position` or
`media_title` on a media player, or `current_temperature` on a climate entity.
A scene created by the `scene.create` service stores every attribute of a
member, including these, and no tolerance can catch them.

Set a tolerance when a value is close but not exact. This is the case for
brightness that round-trips through a percent, a color a bulb converts through
its own gamut, or a cover that estimates its position.

Check the `mismatched_entities` attribute when a member is unavailable, or when
its live state does not report the attribute at all. The suggested tolerance
comes from the other members. Accepting it does not fix a member that is missing
or unavailable, and raising the tolerance does not help either.

To clear an attribute or set a tolerance, open the helper options:

1. Open the helper options.
2. Pick the domain in the dropdown and submit.
3. Clear any attribute that you do not care about, then submit.
4. Read the measured difference in the description, accept the prefilled
   tolerance, and submit.
5. Leave the dropdown empty and submit to save.

Each tolerance uses the scale of the attribute itself. Brightness is 0 to 255,
color temperature is in kelvin, and a media player volume is 0 to 1.

## Sensor states

| State         | Meaning                                                          |
| ------------- | ---------------------------------------------------------------- |
| `on`          | every member matches                                             |
| `off`         | at least one member does not match                               |
| `unknown`     | no member mismatches, but at least one is unavailable or missing |
| `unavailable` | the scene entity is not loaded                                   |

Attributes:

- `scene_entity_id`: the tracked scene.
- `mismatched_entities`: the members that do not match, sorted.

## Installation

[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=pszypowicz&repository=scene_state&category=integration)

Click the button above to open the repository in HACS. Or add it by hand:

1. In HACS, open the menu in the top right, then Custom repositories.
2. Add `https://github.com/pszypowicz/scene_state` with category Integration.

Then install Scene State and restart Home Assistant.

## Configuration

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=scene_state)

Click the button above to start the helper setup. Or start it by hand:

1. Go to Settings, Devices and services, Helpers.
2. Click Create helper and pick Scene State.
3. Select a scene and adjust the grace period and the debounce if needed.

The helper options hold the timers and the comparison rules. The rules are per
domain, and they apply to every member of that domain in the scene.

## Upgrading from 0.0.1

Release 0.0.1 applied built-in tolerances to fourteen attributes. Release 0.1.0
compares exactly until you set a tolerance, so a sensor that reported `on` can
report `off` after the upgrade. Your existing helpers keep their timers. Follow
the steps under When the sensor reports off for each helper that turns off.

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
uv run pre-commit install
scripts/lint
scripts/test
scripts/develop
```

The pre-commit hooks run the formatter, the linter, the type checker, and the
tests before each commit. CI runs the same hooks on all files, so a commit that
passes locally also passes the gate. `scripts/lint` runs all hooks except the
tests on all files.

`scripts/develop` starts Home Assistant from `config/` with the demo
integration and a few sample scenes, and links this component into it.
