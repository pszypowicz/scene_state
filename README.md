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
and it compares them exactly. The sensor is `on` when every member matches its
target.

Devices do not always report back the value that the scene asked for. A light
converts a color through its own gamut. An integration that stores brightness
as a percentage returns 101 when the scene asked for 100. A time-based cover
estimates its position. For each of those, set a tolerance in the helper
options.

Attributes that describe the entity rather than its state never take part.
That covers capability attributes such as `supported_features` and
`effect_list`, and presentation attributes such as `friendly_name` and
`icon`. A light also drops every color representation except one, because it
reports all of them at once and all of them derive from one value.

If the target state is `off` or `closed`, attributes are ignored.

Two timers keep the sensor stable:

- The grace period starts when the scene is activated. Members are compared
  once it ends, so transitions finish first. While it runs, a member change
  does not trigger a comparison. The default is 5 seconds.
- The debounce starts when a member changes. Members are compared once no
  further change arrives within it. The default is 1 second.

### When the sensor reports off

If you do not care about an attribute, clear it. Clearing every attribute of
a domain compares the state string only, so a member in that domain only has
to be on, open, or heating. Clearing is also the only repair for an attribute
that drifts without limit. Examples are `media_position` and `media_title` on
a media player, and `current_temperature` on a climate entity. A scene
created by the `scene.create` service stores every attribute of a member,
including these, and no tolerance can catch them.

If a value is close but not exact, set a tolerance. This is the case for
brightness that a device converts to a percentage and back, for a color that
a bulb converts through its own gamut, and for a cover that estimates its
position.

Check `mismatched_entities` on the sensor to find the member at fault. If that
member is loaded but does not report the attribute at all, it can never
match, and a tolerance does not help. Clear the attribute instead. A member
that is unavailable or missing is a different case. It does not appear in
`mismatched_entities`, and as long as no other member mismatches, the sensor
reports `unknown` rather than `off` until that member comes back.

To clear an attribute or set a tolerance, open the helper options. On the
Helpers page, click the helper, then Configure.

1. Pick the domain in the dropdown and submit. If no domain has anything to
   compare, the dropdown does not appear, and submitting saves and closes.
2. Clear any attribute that you do not care about, then submit.
3. Read the measured difference in the step description.
4. Accept the prefilled tolerance and submit. If the domain has no numeric
   attribute, this step does not appear and you return to the first step.
5. Leave the dropdown empty and submit to save.

Each tolerance uses the scale of the attribute itself. Brightness is 0 to 255,
color temperature is in kelvin, and a media player volume is 0 to 1. A
tolerance of `0` demands an exact match.

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

Release 0.0.1 applied a built-in tolerance to numeric attributes such as
brightness, cover position, and color. Release 0.1.0 compares exactly until
you set a tolerance, so a sensor that reported `on` can report `off` after
the upgrade.

The attribute list also changed. Release 0.0.1 read a fixed per-domain list
and ignored every other stored attribute, and a domain outside that list
compared the state string only. Release 0.1.0 compares every non-metadata
attribute that the scene stores, in every domain. A snapshot scene built with
`scene.create` can now fail on an attribute such as `media_position` or
`current_temperature`. Release 0.0.1 never looked at these, and clearing the
attribute is the repair there.

Release 0.0.1 also limited a desired color temperature to the range the light
reported. That guard is gone. A scene asking for a kelvin outside a bulb's
range now needs a tolerance, even for a light that matched before.

Your existing helpers keep their timers. For each helper that turns off,
follow the steps in [When the sensor reports off](#when-the-sensor-reports-off).

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
