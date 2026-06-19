"""Pinned data.gov.in OGD resources.

Each entry maps an indicator id to ONE OGD resource page on
https://www.data.gov.in/. Operators download the resource's CSV
through that page (the form requires a one-time captcha solve) and
drop the file under
``.runtime/raw/datagovin/<indicator_leaf>.csv``.

The ingest layer reads from that cache; the artifact's ``sources[]``
cites the portal page URL plus the upstream authority page (e.g. the
Rajya Sabha question that produced the dataset).

Why not the OGD JSON API?
-------------------------
See module docstring of :mod:`.parsers` — TL;DR: the documented demo
key caps records at 10/request and 429s after a few pages; a real
key requires SMS-OTP registration we cannot script.
"""
from __future__ import annotations

from dataclasses import dataclass


# Authority page that introduces the OGD platform — second sources[]
# entry so a reader can audit licensing & terms.
OGD_AUTHORITY_URL = "https://www.data.gov.in/"


@dataclass(frozen=True)
class ResourceMeta:
    """One pinned data.gov.in resource."""

    uuid: str
    portal_page_url: str
    authority_page_url: str  # body that produced the underlying answer
    title: str


KNOWN_RESOURCES: dict[str, ResourceMeta] = {
    "fiscal/centre_transfers_gross": ResourceMeta(
        uuid="1f2e77f0-6742-4671-ae29-8836d2110a5c",
        portal_page_url=(
            "https://www.data.gov.in/resource/"
            "state-wise-details-total-revenue-receipts-own-receipts-"
            "and-centre-transfers-available"
        ),
        authority_page_url="https://sansad.in/rs/questions/questions-and-answers",
        title=(
            "State-wise Details of Total Revenue Receipts, with own "
            "Receipts and Centre Transfers (FY17-FY23, Actuals)"
        ),
    ),
    # Reference table (not an indicator) — flat lookup, one row per Post
    # Office, no time axis. Emits to ``datasets/data/entities/pincode.csv``
    # (G8 2026-06-08: was ``datasets/reference/in/pincodes/`` Parquet; the
    # reshape lifted reference entity data into ``data/entities/`` per
    # plan-doc section 9 + flipped to CSV per section 21.2) in Phase A.1.b
    # after the operator captcha-fetches the CSV. The key uses the
    # ``reference/<leaf>`` namespace to make it visually distinct from
    # indicator keys (``fiscal/...``, etc.) in this dict.
    "reference/pincode_directory": ResourceMeta(
        uuid="5c2f62fe-5afa-4119-a499-fec9d604d5bd",
        portal_page_url=(
            "https://www.data.gov.in/resource/"
            "all-india-pincode-directory-till-last-month"
        ),
        authority_page_url="https://www.indiapost.gov.in/",
        title="All India Pincode Directory",
    ),
}


def resource_for(indicator_id: str) -> ResourceMeta | None:
    return KNOWN_RESOURCES.get(indicator_id)
