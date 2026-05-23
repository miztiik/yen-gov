// Public surface of the icon registry. Consumers (Svelte components,
// vite.config.ts) import from here and never reach into the parser /
// allowlist modules directly. This keeps the contract small enough to
// audit at a glance.

export type { Icon, IconAttributes, IconElement, IconElementName, IconRegistry } from "./types";
export { IconParseError, parseIcon } from "./parse";
export {
  ALLOWED_ELEMENTS,
  ALLOWED_ATTRS,
  TOLERATED_ROOT_ATTRS,
  FORBIDDEN_ELEMENTS,
  FORBIDDEN_ATTR_PATTERNS,
  ICON_FILENAME_REGEX,
} from "./allowlist";
