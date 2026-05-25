# data.gov.in OGD Source

**Last Updated**: 2026-05-25

data.gov.in resources have two public faces: the website download button and the API. For agent work, prefer the API. The website `Download` button opens a purpose/captcha modal and is not the repeatable path.

## Agent Contract

One OGD resource is identified by a UUID. The API shape is:

```text
https://api.data.gov.in/resource/<resource_uuid>?api-key=<api_key>&offset=<offset>&limit=<limit>&format=csv
```

Use a caller-provided key or a key already visible in the resource's API/Swagger tab. Keep it in an environment variable while probing; do not commit it. The API requires an `api-key` query parameter.

## Finding the Resource UUID

For a resource page such as `https://www.data.gov.in/resource/<slug>`:

1. Open the page and switch to the `API` tab. The operation path is `/resource/<uuid>`.
2. Fetch `https://www.data.gov.in/backend/dataapi/v1/swagger/<uuid>` to confirm the API contract. It should report host `api.data.gov.in`, path `/resource/<uuid>`, and parameters `api-key`, `format`, `offset`, `limit`.
3. If the page is hard to inspect, run `python tools/datagovin_recon.py <resource-slug>` and use the UUID it prints.

The resource page may also contain a catalog UUID. Do not confuse it with the resource UUID; the API endpoint uses the resource UUID.

## Probe Before Download

First request metadata, not the full file:

```text
format=json&offset=0&limit=1
```

Record these from the response:

- `total`: expected data-row count.
- `records[0]` keys: expected columns.
- `title`, `org`, `updated_date`: source-context fields for later provenance work.

Then request a tiny CSV page:

```text
format=csv&offset=0&limit=5
```

Verify the response is `text/csv` and the header matches the JSON keys.

## Paged CSV Download

Use integer `limit` and `offset`. Do not rely on `limit=all`; it is not stable for larger resources. A verified conservative default is:

```text
limit=10000
offset=0,10000,20000,...
format=csv
```

Wait about 60 seconds between pages for large resources. If a page times out or returns `429`, keep the last complete partial file and resume from the number of already-written data rows.

When joining pages:

- Write the header once.
- Drop the repeated header from later pages.
- Validate every page header is identical.
- Stop only when assembled data rows equal the JSON `total`.

Write operator-fetched or API-fetched CSVs to `.runtime/raw/datagovin/<leaf>.csv`. This is an ephemeral operator cache, not a committed dataset.

## Verified Example

Resource: All India Pincode Directory till last month

- Resource page: `https://www.data.gov.in/resource/all-india-pincode-directory-till-last-month`
- Resource UUID: `5c2f62fe-5afa-4119-a499-fec9d604d5bd`
- Output cache: `.runtime/raw/datagovin/pincode_directory.csv`
- Verified rows: `165627`
- Verified columns: `circlename`, `regionname`, `divisionname`, `officename`, `pincode`, `officetype`, `delivery`, `district`, `statename`, `latitude`, `longitude`
- Working page size: `limit=10000`
- Delay used: `60s` between page requests

Larger pages such as `limit=50000` can work for small probes but may time out while reading the response. `format=csv&format=xml` resolves as XML on this portal; pass one `format` value only.

## What Not To Use

- Browser `Download` button: opens a captcha-gated purpose modal.
- DMS backend guesses such as `/backend/dms/v1/ogdp/resource/download/<uuid>`: observed timing out for the pincode resource.
- `limit=all` for large CSV pulls: observed unreliable.

## See Also

- [`data-sources.md`](../../reference/data-sources.md) — source catalogue entry.
- [`boundary-data-sources.md`](../../reference/boundary-data-sources.md) — pincode source notes.
- [`backend/yen_gov/sources/datagovin_ogd/urls.py`](../../../backend/yen_gov/sources/datagovin_ogd/urls.py) — pinned resource metadata.
- [`tools/datagovin_recon.py`](../../../tools/datagovin_recon.py) — resource page UUID probe.