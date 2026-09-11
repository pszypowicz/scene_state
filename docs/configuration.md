# Configuration

## Create a helper

1. Go to Settings, Devices and services, Helpers.
2. Click Create helper and pick Scene State.
3. Select a scene.
4. Adjust the grace period and the debounce if needed.
5. Give the helper a name if you want one.

The sensor is named `Scene state <title>`. The title is the scene's own name
unless you set one on the create form. Every sensor groups together in the
entity picker whatever the scene itself is called.

You can create more than one helper for the same scene. Give each one a name to
tell them apart, for example one with a tight tolerance and one with a loose
one.

You can rename a helper later, from its menu on the Helpers page. That changes
the title. The entity id never changes. The displayed name of the sensor picks
up the new title after the entry reloads.

## Timers

- The grace period starts when the scene is activated. Members are compared
  once it ends, so transitions finish first. While it runs, a change of a member
  does not trigger a comparison. The default is 5 seconds.
- The debounce starts when a member changes. Members are compared once no
  further change arrives within it. The default is 1 second.

## Matching rules

The helper compares the attributes that the scene stores, and it compares them
exactly. If the target state is `off` or `closed`, attributes are ignored.

Attributes that describe the entity rather than its state never take part. That
covers capability attributes such as `supported_features` and `effect_list`,
and presentation attributes such as `friendly_name` and `icon`. A light also
drops every color representation except one, because it reports all of them at
once and all of them derive from one value.

Devices do not always report back the value that the scene asked for. A light
converts a color through its own gamut. An integration that stores brightness
as a percentage returns 101 when the scene asked for 100. A time based cover
estimates its position. For each of those, set a tolerance.

The rules are per domain, and they apply to every member of that domain in the
scene.

## Change the rules

To clear an attribute or to set a tolerance, open the helper options. On the
Helpers page, click the helper, then Configure.

1. Pick the domain in the dropdown and submit. If no domain has anything to
   compare, the dropdown does not appear, and a submit saves and closes.
2. Clear any attribute that you do not care about, then submit.
3. Read the measured difference in the step description.
4. Accept the prefilled tolerance and submit. If the domain has no numeric
   attribute, this step does not appear and you return to the first step.
5. Leave the dropdown empty and submit to save.

Each tolerance uses the scale of the attribute itself. Brightness is 0 to 255,
color temperature is in kelvin, and the volume of a media player is 0 to 1. A
tolerance of `0` demands an exact match.

## Localization

Scene State ships English and Polish. The displayed name of the sensor is
translated. A Polish Home Assistant shows `Stan sceny <title>` where an English
one shows `Scene state <title>`. Home Assistant gives some languages, Polish
among them, their own entity ids instead of a fallback to English. A Polish
instance gets an id such as `binary_sensor.stan_sceny_<title>`. An English one
keeps `binary_sensor.scene_state_<title>`.

An entity id is fixed when the entity is first created, and Home Assistant
never derives it again. A later change of the interface language leaves your
existing sensors alone. Only a helper that you create after the change picks up
the new language. An id is therefore safe to reference from a dashboard or an
automation once it exists.
