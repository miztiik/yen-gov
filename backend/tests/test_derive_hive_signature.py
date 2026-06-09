"""Tier-A unit tests locking the ``derive_hive`` signature contract after
the Hans+Max+Gregor converged verdict (2026-06-09, Item 1 of the G10
follow-on reconciliation).

The contract:

1. Parameter rename ``state`` -> ``state_slug``. Forces every caller
   through the type-checker; an accidental ``state=`` pass becomes a
   TypeError at call site.
2. ``state_slug`` is embedded verbatim in the ``state=<value>`` Hive
   segment. The pre-2026-06-09 ``f"in_{state.lower()}"`` literal is
   gone; partitions never carry the legacy ``in_<lc>`` ECI-derived
   prefix.
3. ``state_slug`` matching ``^[SU][0-9]{2}$`` raises ``ValueError``.
   Catches an accidental ECI-code pass-through (a regression that
   would otherwise silently re-emit ``state=s22/`` paths).
4. Hyphenated slugs (``dadra-and-nagar-haveli-and-daman-and-diu``)
   pass verbatim and validate against boundary-layers.schema.json v1.5
   (regex widened to ``[a-z0-9_-]+``).
5. ``_eci_to_slug("S22")`` round-trips to ``"tamil-nadu"`` (and other
   spot-checked ECI codes) reading from
   ``datasets/taxonomy/lgd_states.json``.

Per CLAUDE.md sect 15 and Holy Law #7: pure signature + behaviour
testing of an in-process function. No mocks; the lgd_states.json read
happens against the real on-disk file because the helper's whole point
is to source from the canonical store.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tools.boundaries._paths import _eci_to_slug, derive_hive  # noqa: E402


# ----------------------------------------------------------------------
# 1. Signature shape
# ----------------------------------------------------------------------


def test_derive_hive_param_name_is_state_slug_not_state() -> None:
    """Lock the parameter rename: derive_hive's state-shard input is
    named ``state_slug`` (not the pre-2026-06-09 ``state``). Forces
    every caller through the type-checker on the rename PR.
    """
    sig = inspect.signature(derive_hive)
    params = list(sig.parameters)
    assert "state_slug" in params, (
        f"derive_hive must have a ``state_slug`` parameter; got {params}"
    )
    assert "state" not in params, (
        "derive_hive must NOT have a ``state`` parameter (pre-2026-06-09 "
        f"name); got {params}. Callers holding an ECI code must call "
        "_eci_to_slug() and pass via state_slug="
    )


# ----------------------------------------------------------------------
# 2. ECI-shape rejection
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "ecish",
    [
        "S22",
        "S01",
        "S11",
        "S29",
        "U05",
        "U02",
        "U08",
        "U09",
    ],
)
def test_derive_hive_rejects_eci_shape_on_state_slug(ecish: str) -> None:
    """state_slug matching ``^[SU][0-9]{2}$`` raises ValueError. Catches
    an accidental ECI-code pass-through at the boundary; callers MUST
    call _eci_to_slug() first.
    """
    with pytest.raises(ValueError, match=r"matches the ECI state-code shape"):
        derive_hive(
            kind="ac",
            delim="2008",
            state_slug=ecish,
        )


# ----------------------------------------------------------------------
# 3. Slug verbatim emission
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("slug", "expected_path", "expected_layer_id"),
    [
        (
            "tamil-nadu",
            "boundaries/electoral/delim=2008/ac/state=tamil-nadu/all.geojson",
            "boundaries.electoral.delim=2008.ac.state=tamil-nadu",
        ),
        (
            "delhi",
            "boundaries/electoral/delim=2008/ac/state=delhi/all.geojson",
            "boundaries.electoral.delim=2008.ac.state=delhi",
        ),
        (
            "andhra-pradesh",
            "boundaries/electoral/delim=2008/ac/state=andhra-pradesh/all.geojson",
            "boundaries.electoral.delim=2008.ac.state=andhra-pradesh",
        ),
        (
            "dadra-and-nagar-haveli-and-daman-and-diu",
            (
                "boundaries/electoral/delim=2008/ac/"
                "state=dadra-and-nagar-haveli-and-daman-and-diu/all.geojson"
            ),
            (
                "boundaries.electoral.delim=2008.ac."
                "state=dadra-and-nagar-haveli-and-daman-and-diu"
            ),
        ),
    ],
)
def test_derive_hive_embeds_slug_verbatim_for_electoral(
    slug: str,
    expected_path: str,
    expected_layer_id: str,
) -> None:
    """Hyphenated LGD-name slugs embed verbatim into ``state=<value>``;
    boundary-layers.schema.json v1.5 regex ``[a-z0-9_-]+`` accepts them.
    No more legacy ``in_<lc>`` prefix.
    """
    partition_path, layer_id = derive_hive(
        kind="ac",
        delim="2008",
        state_slug=slug,
    )
    assert partition_path == expected_path
    assert layer_id == expected_layer_id


def test_derive_hive_admin_spine_also_embeds_slug_verbatim() -> None:
    """The signature rename is UNIVERSAL (not just ac/pc) per Gregor's
    option (v). Admin-spine kinds also embed ``state_slug`` verbatim.
    """
    partition_path, layer_id = derive_hive(
        kind="villages",
        state_slug="tamil-nadu",
        district_lgd="603",
    )
    assert partition_path == (
        "boundaries/in/villages/state=tamil-nadu/district=603/all.geojson"
    )
    assert layer_id == (
        "boundaries.in.villages.state=tamil-nadu.district=603"
    )


# ----------------------------------------------------------------------
# 4. _eci_to_slug round-trip
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("eci_code", "expected_slug"),
    [
        ("S22", "tamil-nadu"),
        ("S01", "andhra-pradesh"),
        ("S11", "kerala"),
        ("S29", "telangana"),
        ("U05", "delhi"),
        ("U02", "chandigarh"),
        ("U08", "jammu-and-kashmir"),
        ("U03", "dadra-and-nagar-haveli-and-daman-and-diu"),
    ],
)
def test_eci_to_slug_canonical_mapping(eci_code: str, expected_slug: str) -> None:
    """``_eci_to_slug`` round-trips canonical ECI codes to LGD-name
    slugs via ``datasets/taxonomy/lgd_states.json`` (the same source
    ``writer.py::_eci_to_lgd_slug_case_sql`` reads from per ADR-0050).
    """
    assert _eci_to_slug(eci_code) == expected_slug


def test_eci_to_slug_rejects_unknown_code() -> None:
    """A typoed or unseeded ECI code raises ValueError with a clear
    message pointing at the canonical source file.
    """
    with pytest.raises(ValueError, match=r"unknown ECI state code"):
        _eci_to_slug("S99")
