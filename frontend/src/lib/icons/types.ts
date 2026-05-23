// Public types for the icon registry. Both the build-time Vite plugin (which
// parses SVG files at build/dev and emits a typed registry) and the runtime
// consumer (TopicIcon.svelte and any future icon renderer) import from
// here. Keeping the shape in one file prevents the parallel-grammar drift
// the chart plan rejects.
//
// Design rule per the chart plan §1.3:
//   * Structured shape only — never a raw SVG string. The runtime cannot
//     emit `<script>` even if the parser ever regressed, because the type
//     has no slot for it.
//   * `name` is the kebab-case filename without the `.svg` extension; the
//     plugin enforces the filename regex `^[a-z0-9]+(-[a-z0-9]+)*$`.

export type IconElementName =
  | "g"
  | "path"
  | "circle"
  | "rect"
  | "line"
  | "polyline"
  | "polygon";

export type IconAttributes = Readonly<Record<string, string>>;

export interface IconElement {
  readonly name: IconElementName;
  readonly attrs: IconAttributes;
  readonly children: readonly IconElement[];
}

export interface Icon {
  readonly name: string;
  readonly viewBox: string;
  readonly children: readonly IconElement[];
}

export type IconRegistry = Readonly<Record<string, Icon>>;
