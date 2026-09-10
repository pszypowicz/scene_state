"""Compare a desired scene state with the current state of an entity."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import math
from typing import Any, Self

from homeassistant.core import State

from .attributes import comparable, selection_name
from .const import CONF_COMPARE, RESERVED_OPTION_KEYS

type Comparator = Callable[[Any, Any], bool]

STATES_WITHOUT_ATTRIBUTES: frozenset[str] = frozenset({"off", "closed"})
FLOAT_MARGIN = 1e-9


@dataclass(frozen=True, slots=True)
class MatchResult:
    """Outcome of one comparison."""

    matches: bool
    reason: str | None = None


def _finite_tolerance(number: float) -> float | None:
    """Return the number as a usable tolerance, or None when it cannot serve as one.

    A negative tolerance would make an exactly equal value mismatch, so it is
    clamped to zero instead. A number too large to become a float raises
    OverflowError on conversion, and `from_options` must never raise during
    entry setup, so such a number is dropped instead of propagated.
    """
    try:
        value = float(number)
    except OverflowError:
        return None
    return max(0.0, value) if math.isfinite(value) else None


@dataclass(frozen=True, slots=True)
class MatchProfile:
    """The comparison rules of one config entry.

    A domain that is absent from `compare` has no stored selection, and every
    comparable attribute of that domain counts. An empty selection is different,
    and it compares the state string only.

    The selection and the tolerance key different names for a light color
    attribute. `compares` folds the attribute name through `selection_name`, so
    every color representation shares one selection under "color". `tolerance`
    looks up the raw attribute name instead, because `hs_color` and `xy_color`
    do not share a scale and need separate numbers.
    """

    compare: Mapping[str, frozenset[str]]
    tolerances: Mapping[str, Mapping[str, float]]

    @classmethod
    def from_options(cls, options: Mapping[str, Any]) -> Self:
        """Read the per-domain rules from the options of a config entry."""
        compare: dict[str, frozenset[str]] = {}
        tolerances: dict[str, Mapping[str, float]] = {}
        for key, value in options.items():
            if key in RESERVED_OPTION_KEYS or not isinstance(value, Mapping):
                continue
            selection = value.get(CONF_COMPARE)
            if not isinstance(selection, list | tuple):
                continue
            compare[key] = frozenset(str(name) for name in selection)
            tolerances[key] = {
                str(name): tolerance
                for name, number in value.items()
                if name != CONF_COMPARE
                and isinstance(number, int | float)
                and not isinstance(number, bool)
                and (tolerance := _finite_tolerance(number)) is not None
            }
        return cls(compare, tolerances)

    def compares(self, domain: str, attribute: str) -> bool:
        """Return whether the attribute takes part in the comparison."""
        selection = self.compare.get(domain)
        if selection is None:
            return True
        return selection_name(attribute, domain) in selection

    def tolerance(self, domain: str, attribute: str) -> float | None:
        """Return the tolerance of the attribute, or None for an exact match."""
        return self.tolerances.get(domain, {}).get(attribute)


def _within(tolerance: float) -> Comparator:
    def compare(wanted: Any, got: Any) -> bool:
        if isinstance(wanted, bool) or isinstance(got, bool):
            # float(True) is 1.0, so a boolean would otherwise take the numeric
            # path below and a tolerance of 1 would make True match False.
            return bool(wanted == got)
        try:
            difference = abs(float(wanted) - float(got))
        except TypeError, ValueError:
            # A tolerance means nothing for a value that is not a number.
            return bool(wanted == got)
        # Float subtraction can exceed the tolerance by a rounding error.
        return difference <= tolerance + FLOAT_MARGIN

    return compare


def _sequence_within(tolerance: float) -> Comparator:
    def compare(wanted: Any, got: Any) -> bool:
        if isinstance(wanted, str) or isinstance(got, str):
            return False
        if not isinstance(wanted, Sequence) or not isinstance(got, Sequence):
            return False
        if len(wanted) != len(got):
            return False
        inner = _within(tolerance)
        return all(
            inner(wanted_item, got_item)
            for wanted_item, got_item in zip(wanted, got, strict=True)
        )

    return compare


def _comparator(wanted: Any, tolerance: float | None) -> Comparator:
    """Return the comparator for one desired value.

    A scene stores a color as a list, and a light reports it as a tuple, so a
    non-string sequence compares element by element. An absent tolerance is a
    margin of zero, which demands equality.
    """
    margin = 0.0 if tolerance is None else tolerance
    if not isinstance(wanted, str) and isinstance(wanted, Sequence):
        return _sequence_within(margin)
    return _within(margin)


def match_state(desired: State, current: State, profile: MatchProfile) -> MatchResult:
    """Return whether the current state satisfies the desired state."""
    if desired.state != current.state:
        return MatchResult(False, f"state: wanted {desired.state}, got {current.state}")
    if desired.state in STATES_WITHOUT_ATTRIBUTES:
        return MatchResult(True)

    domain = desired.domain
    for attribute in comparable(desired):
        if not profile.compares(domain, attribute):
            continue
        wanted = desired.attributes[attribute]
        got = current.attributes.get(attribute)
        if got is None:
            return MatchResult(False, f"{attribute}: wanted {wanted}, got nothing")
        compare = _comparator(wanted, profile.tolerance(domain, attribute))
        if not compare(wanted, got):
            return MatchResult(False, f"{attribute}: wanted {wanted}, got {got}")
    return MatchResult(True)
