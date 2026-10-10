"""Display-only formatting helpers for source-backed labels."""

from __future__ import annotations


def display_osm_name(value: object) -> str | None:
    """Return an OSM name for display without changing source matching or IDs.

    Some OSM road names are stored entirely in upper case (for example,
    ``M.G.ROAD``).  Title casing those names is a presentation concern only;
    cache values, identifiers, and name matching deliberately remain untouched.
    """
    if not isinstance(value, str):
        return None
    name = value.strip()
    if not name:
        return None
    return name.title() if name.isupper() else name
