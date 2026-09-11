# Scene State

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/pszypowicz/scene_state)](https://github.com/pszypowicz/scene_state/releases)
[![Home Assistant](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fpszypowicz%2Fscene_state%2Fmain%2Fhacs.json&query=%24.homeassistant&label=Home%20Assistant&color=41BDF5&prefix=%E2%89%A5)](https://www.home-assistant.io)
[![CI](https://github.com/pszypowicz/scene_state/actions/workflows/ci.yml/badge.svg)](https://github.com/pszypowicz/scene_state/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/pszypowicz/scene_state)](LICENSE)

[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=pszypowicz&repository=scene_state&category=integration)

A Home Assistant helper that answers one question for a scene: do all entities
in the scene match the states that the scene defines?

Home Assistant scenes are stateless. The scene entity only records when it was
last activated. This helper adds a binary sensor per scene. The sensor is `on`
while every entity in the scene matches its target, and `off` as soon as one of
them drifts away.

## How it works

The helper reads the target states from the scene and compares them with the
current entity states. It compares only the attributes that the scene stores,
and it compares them exactly. In the helper options you can clear an attribute
that you do not care about, and set a tolerance for a value that a device
reports back with a small difference.

Two timers keep the sensor stable. The grace period starts when the scene is
activated, so transitions finish before the first comparison. The debounce
starts when a member changes, and it waits for further changes.

| State         | Meaning                                                          |
| ------------- | ---------------------------------------------------------------- |
| `on`          | every member matches                                             |
| `off`         | at least one member does not match                               |
| `unknown`     | no member mismatches, but at least one is unavailable or missing |
| `unavailable` | the scene entity is not loaded                                   |

The sensor carries two attributes. `scene_entity_id` names the tracked scene.
`mismatched_entities` lists the members that do not match.

## Installation

Click the HACS badge at the top of this page to open the repository in HACS.
Install Scene State, then restart Home Assistant.

## Configuration

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=scene_state)

Click the button above to start the helper setup. Select a scene, then adjust
the grace period and the debounce if needed.

## Documentation

- [Configuration](https://github.com/pszypowicz/scene_state/blob/main/docs/configuration.md):
  the matching rules, the tolerances, the timers, and the name of the sensor.
- [Troubleshooting](https://github.com/pszypowicz/scene_state/blob/main/docs/troubleshooting.md):
  what to do when the sensor reports `off` and you expect `on`.
- [Development](https://github.com/pszypowicz/scene_state/blob/main/docs/development.md):
  how to run the checks and a local Home Assistant.

## Limitations

- Only scenes defined in Home Assistant are supported, from the scene editor or
  from `scenes.yaml`. Scenes that live on a hub, for example Hue or KNX scenes,
  do not expose their targets to Home Assistant.
- Scenes defined in YAML without an `id` have no entity registry entry. A
  rename or removal of such a scene does not update or remove the helper.
- The sensor does not control the scene. Use the scene entity to activate it.
