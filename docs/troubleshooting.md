# Troubleshooting

## The sensor reports off

Read `mismatched_entities` on the sensor to find the member at fault. Then pick
one of the two repairs below.

A member that is unavailable or missing is a different case. It does not appear
in `mismatched_entities`. As long as no other member mismatches, the sensor
reports `unknown` rather than `off` until that member comes back.

### Clear the attribute

If you do not care about an attribute, clear it. Clearing every attribute of a
domain compares the state string only, so a member in that domain only has to
be on, open, or heating.

Clearing is also the only repair for an attribute that drifts without limit.
Examples are `media_position` and `media_title` on a media player, and
`current_temperature` on a climate entity. A scene created by the
`scene.create` service stores every attribute of a member, including these, and
no tolerance can catch them.

A loaded member that does not report the attribute at all can never match. A
tolerance does not help there. Clear the attribute instead.

### Set a tolerance

If a value is close but not exact, set a tolerance. This is the case for
brightness that a device converts to a percentage and back, for a color that a
bulb converts through its own gamut, and for a cover that estimates its
position.

A scene that asks for a color temperature outside the range of a bulb also
needs a tolerance, because the bulb reports the nearest kelvin that it can
reach.

See [Configuration](configuration.md) for the steps that clear an attribute or
set a tolerance.
