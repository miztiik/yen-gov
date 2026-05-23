// Single source of truth for the SVG allowlist. The Vite plugin (build) AND
// the vitest assertions (test) import from this file. There is no second
// copy of these sets anywhere in the codebase — drift between plugin and
// test was the 2026-05-16 lesson and is reproduced here intentionally as a
// single export to make divergence impossible.

import type { IconElementName } from "./types";

// Elements allowed inside an icon SVG. The root `<svg>` is parsed as a
// container and stripped (its allowed attrs become the Icon's viewBox);
// every nested element here MUST be one of the names below or the build
// FAILS LOUDLY with a precise file:line message. Stripping silently would
// launder a contributor's intent.
export const ALLOWED_ELEMENTS: ReadonlySet<IconElementName> = new Set([
  "g",
  "path",
  "circle",
  "rect",
  "line",
  "polyline",
  "polygon",
] as const);

// Attributes allowed on any allowed element. Drawing-shape data only —
// nothing that loads remote content, fires events, embeds HTML islands, or
// sets a hard pixel size (the parent CSS class controls size; tinting goes
// through `currentColor`).
export const ALLOWED_ATTRS: ReadonlySet<string> = new Set([
  "viewBox",
  "fill",
  "stroke",
  "stroke-width",
  "stroke-linecap",
  "stroke-linejoin",
  "fill-rule",
  "clip-rule",
  "d",
  "cx",
  "cy",
  "r",
  "x",
  "y",
  "x1",
  "x2",
  "y1",
  "y2",
  "points",
  "transform",
] as const);

// Attributes on the <svg> root that are tolerated but DROPPED before the
// Icon is materialised. `width` and `height` would override the consumer's
// CSS sizing; `xmlns` is meaningless in inline SVG-in-HTML and survives
// only because Lucide files ship with it. Anything else on the root
// triggers the same loud rejection as a forbidden nested attribute.
export const TOLERATED_ROOT_ATTRS: ReadonlySet<string> = new Set([
  "width",
  "height",
  "xmlns",
  "xmlns:xlink",
  "fill",
  "stroke",
  "stroke-width",
  "stroke-linecap",
  "stroke-linejoin",
  "class",
] as const);

// Elements that, if observed anywhere in the SVG, REJECT the build outright
// with an explicit error referencing the contributor's file. These are not
// "strip then proceed" — silent stripping would let a contributor smuggle
// intent past code-review.
export const FORBIDDEN_ELEMENTS: ReadonlySet<string> = new Set([
  "script",
  "style",
  "foreignObject",
  "image",
  "use",
  "a",
  "iframe",
  "object",
  "embed",
  "audio",
  "video",
  "animate",
  "animateMotion",
  "animateTransform",
  "set",
] as const);

// Attribute name patterns that REJECT the build outright. Event handlers,
// xlink:* references, and inline `style` (which can hold expressions in
// some legacy contexts) are all blocked. The match is case-insensitive.
export const FORBIDDEN_ATTR_PATTERNS: readonly RegExp[] = [
  /^on/i, // onclick, onload, onerror, …
  /^xlink:/i, // xlink:href can load remote content
  /^href$/i, // <use href=…> / <a href=…>
  /^style$/i,
] as const;

// Filename regex. Pinned here so the plugin and any contributor tooling
// agree on what a valid icon filename is. Underscore-prefixed names
// (e.g. `_README.svg`) and `__fixtures__/` paths are skipped by the
// plugin's directory walker, not by this regex.
export const ICON_FILENAME_REGEX = /^[a-z0-9]+(-[a-z0-9]+)*$/;
