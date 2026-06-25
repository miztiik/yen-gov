// Pure placement helper for the standard map hover card
// (standard-map-hover-card plan, Row 2). Given the cursor position inside a
// chart container and the FIXED card size, it returns the card's top-left
// offset so the constant-size box (R-A 256x140) never clips or squeezes at a
// container edge: it anchors bottom-right of the cursor, flips to the LEFT
// when it would overflow the right edge, flips UP when it would overflow the
// bottom edge, then clamps inside the container. Pure + node-testable: no DOM,
// no Svelte - `HoverCardShell.svelte` is the only DOM consumer.

export interface HoverCardPositionInput {
  /** Cursor x within the container (px). */
  cursorX: number;
  /** Cursor y within the container (px). */
  cursorY: number;
  /** Container width (px). */
  containerW: number;
  /** Container height (px). */
  containerH: number;
  /** Fixed card width (px). Default 256 (R-A). */
  cardW?: number;
  /** Fixed card height (px). Default 140 (R-A). */
  cardH?: number;
  /** Gap between the cursor and the card (px). Default 12. */
  offset?: number;
}

export interface HoverCardPosition {
  /** Card left offset within the container (px). */
  left: number;
  /** Card top offset within the container (px). */
  top: number;
}

export function computeHoverCardPosition({
  cursorX,
  cursorY,
  containerW,
  containerH,
  cardW = 256,
  cardH = 140,
  offset = 12,
}: HoverCardPositionInput): HoverCardPosition {
  // Default anchor: bottom-right of the cursor.
  let left = cursorX + offset;
  let top = cursorY + offset;

  // Flip LEFT when the card would overflow the container's right edge.
  if (cursorX + offset + cardW > containerW) {
    left = cursorX - offset - cardW;
  }

  // Flip UP when the card would overflow the container's bottom edge.
  if (cursorY + offset + cardH > containerH) {
    top = cursorY - offset - cardH;
  }

  // Clamp so the fixed-size box always stays fully inside the container.
  // When the container is smaller than the card the max collapses to 0.
  const maxLeft = Math.max(0, containerW - cardW);
  const maxTop = Math.max(0, containerH - cardH);
  left = Math.min(Math.max(left, 0), maxLeft);
  top = Math.min(Math.max(top, 0), maxTop);

  return { left, top };
}
