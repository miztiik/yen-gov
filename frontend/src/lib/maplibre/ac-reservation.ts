/**
 * AC reservation status, read off a boundary feature's raw properties.
 *
 * The source is heterogeneous across the constituency topojson files:
 *  - some states carry an explicit `reservation` field ("GEN"/"SC"/"ST",
 *    e.g. Assam);
 *  - others encode it only as an `(SC)`/`(ST)` suffix on `ac_name`
 *    (e.g. Tamil Nadu, Karnataka).
 *
 * Reservation lives nowhere else in the data layer — neither dim_acs nor
 * the winner rows carry it — so the tooltip reads it straight off the
 * hovered feature. Returns "SC"/"ST" or null; "GEN" and anything unknown
 * collapse to null (the tooltip card suppresses the tag for those).
 */
export function parseReservation(
  props: Record<string, unknown>,
): "SC" | "ST" | null {
  const explicit = String(props.reservation ?? "")
    .trim()
    .toUpperCase();
  if (explicit === "SC" || explicit === "ST") return explicit;

  const name = String(props.ac_name ?? "");
  const m = /\((SC|ST)\)\s*$/i.exec(name);
  if (m) return m[1].toUpperCase() as "SC" | "ST";

  return null;
}
