// Type declaration for the virtual module emitted by the Vite plugin
// `iconRegistryPlugin` (defined in frontend/vite.config.ts). The plugin
// walks frontend/src/lib/icons/*.svg at build/dev time, parses each file
// through the strict allowlist (frontend/src/lib/icons/parse.ts), and
// emits a frozen `IconRegistry` keyed by the filename stem.
//
// Consumers import { iconRegistry } from "virtual:icon-registry" and get
// a fully-typed registry without taking a runtime dependency on the
// parser. The parser only runs at build/dev — never in the citizen's
// browser bundle.

declare module "virtual:icon-registry" {
  import type { IconRegistry } from "./types";
  export const iconRegistry: IconRegistry;
}
