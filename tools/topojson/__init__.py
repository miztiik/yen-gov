"""tools.topojson - GeoJSON to TopoJSON converter.

Per TODO/20260531-geojson-to-topojson-migration-plan.md P2.1 (Fowler).
Subprocess wrapper around mapshaper CLI (installed as a frontend devDep via
`bunx mapshaper`; bun.lock is the version contract).
"""
