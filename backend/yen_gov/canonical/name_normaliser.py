"""Shared entity-name normaliser for resolver-side name matching.

Used by the canonical reingest layer (parliament/assembly ECI ingest) to
resolve a publisher-emitted entity name (e.g. ECI ``Bangalore North``,
``JANJGIR-CHAMPA``, ``Mumbai South-Central``) to its LGD-canonical row on
``datasets/data/entities/electoral.csv``.

The contract (Hans verdict 2026-06-09, per the G16 alias backfill PR):
``normalise_entity_name`` MUST collapse three drift axes:

1. **Case** - publisher capitalisation varies (``Bangalore`` vs ``BANGALORE``
   vs ``bangalore``).
2. **Whitespace runs** - leading / trailing / internal multi-space runs
   collapse to a single space.
3. **Hyphen / underscore / inter-word punctuation** - ECI vs LGD often differ
   on whether a compound PC name is hyphenated or space-separated
   (``Mumbai North-East`` vs ``Mumbai North East``; ``Bardhaman-Durgapur`` vs
   ``Bardhaman - Durgapur``). All of ``-``, ``_``, ``\u2013``, ``\u2014``
   collapse to a single space alongside whitespace.

Out of scope:

- **Semantic renames** (Bengaluru vs Bangalore, Pataliputra vs Patliputra,
  Mahabubnagar vs Mahbubnagar). Those bind via the ``aliases`` column on
  ``electoral.csv``, not via this normaliser. See
  ``docs/concepts/electoral-hierarchy.md`` "Alias policy".
- **Transliteration normalisation** (Devanagari <-> Latin). Out of scope.
- **Diacritic stripping**. The 4189 AC + 530 PC spine is ASCII; if a future
  publisher emits a diacritic-bearing name we add a targeted alias.

See ``backend/tests/test_name_normaliser.py`` for the round-trip invariants
this contract guarantees against the 36 BOUND G16 LS2024 alias pairs.
"""

from __future__ import annotations

import re

# Whitespace, hyphen, underscore, en-dash, em-dash all collapse to single space.
# The character class is fixed at module load to avoid per-call recompile cost.
_PUNCT_COLLAPSE_RE = re.compile(r"[\s\-_\u2013\u2014]+")


def normalise_entity_name(name: str) -> str:
    """Lowercase + strip + collapse [whitespace|hyphen|underscore|dashes] runs to single space.

    ``None`` and the empty string both map to the empty string (callers
    typically gate on the normalised key being non-empty rather than raising
    here - keeps the helper pure-data so it can be reused at the ingest
    boundary, where empty names are filtered upstream).

    Examples (verified by ``test_name_normaliser.py``):
        >>> normalise_entity_name("Bangalore North")
        'bangalore north'
        >>> normalise_entity_name("BANGALORE NORTH")
        'bangalore north'
        >>> normalise_entity_name("Bangalore  North")  # collapsed double-space
        'bangalore north'
        >>> normalise_entity_name("Mumbai North-East")
        'mumbai north east'
        >>> normalise_entity_name("Mumbai North East")
        'mumbai north east'
        >>> normalise_entity_name("JANJGIR-CHAMPA")
        'janjgir champa'
        >>> normalise_entity_name("  Bardhaman - Durgapur  ")
        'bardhaman durgapur'
    """
    if not name:
        return ""
    return _PUNCT_COLLAPSE_RE.sub(" ", name.strip().lower()).strip()
