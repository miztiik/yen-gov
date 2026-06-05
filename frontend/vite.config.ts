/// <reference types="vitest" />
import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { fileURLToPath } from "node:url";
import { resolve, extname, sep } from "node:path";
import { readFileSync, readdirSync, statSync, existsSync, writeFileSync } from "node:fs";
import { execSync } from "node:child_process";
import { parseIcon, ICON_FILENAME_REGEX, type Icon } from "./src/lib/icons";

// Repo root = parent of frontend/. Used by both the dev middleware (which
// serves datasets/ in place — per CLAUDE.md §4 the frontend MUST NOT commit
// data files, and per the user's "no copy" choice we don't even copy at
// build time) and by the deploy step (Phase 4) which uploads frontend/dist
// alongside datasets/ to a single Pages root.
const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..");

// Map file extension → Content-Type. Anything not listed defaults to
// application/octet-stream (correct for opaque binaries).
const CONTENT_TYPES: Record<string, string> = {
  ".json": "application/json; charset=utf-8",
  ".csv": "text/csv; charset=utf-8",
  ".geojson": "application/geo+json; charset=utf-8",
  ".parquet": "application/vnd.apache.parquet",
};

// In-place serve of <repoRoot>/datasets at the URL prefix /data/. Production
// builds expect the same /data/ prefix to resolve via the Pages deploy
// layout (docs/architecture/frontend/data-loading.md).
function serveDatasets() {
  return {
    name: "yen-gov-serve-datasets",
    configureServer(server: any) {
      const datasetsRoot = resolve(repoRoot, "datasets");
      server.middlewares.use("/data", (req: any, res: any, _next: any) => {
        const url = req.url?.split("?")[0] ?? "/";
        const target = resolve(datasetsRoot, "." + url);
        // Path traversal guard: target must stay inside datasets/.
        if (target !== datasetsRoot && !target.startsWith(datasetsRoot + sep)) {
          res.statusCode = 403;
          return res.end("forbidden");
        }
        try {
          const stat = statSync(target);
          if (stat.isDirectory()) {
            res.statusCode = 404;
            return res.end("not found");
          }
          const ext = extname(target).toLowerCase();
          res.setHeader("Content-Type", CONTENT_TYPES[ext] ?? "application/octet-stream");
          res.setHeader("Content-Length", String(stat.size));
          return res.end(readFileSync(target));
        } catch {
          // Do NOT fall through to next() — that lets the SPA HTML answer
          // /data/ 404s with a 200, masking missing-file bugs in dev.
          res.statusCode = 404;
          return res.end("not found");
        }
      });
    },
  };
}

// Deployed base path. Defaults to "/" for `bun run dev` / `bun run preview`
// and any root-served prod environment (custom domain, user/org Pages,
// CDN). The deploy workflow sets BASE_URL=/yen-gov/ so emitted asset URLs
// and runtime data URLs (frontend/src/lib/paths.ts) resolve under the
// project Pages subpath. Keep this an env var, not a hardcode - repo name
// is a deployment concern, not a source-code one (CLAUDE.md section 6).
const BASE_URL = process.env.BASE_URL ?? "/";

// Build-time SHA + date injection (plan section 21.8 footer line; U2c).
// LeftRail.svelte renders a muted "build <sha7> . <date>" line in the
// footer linking to the GitHub commit URL so any deployed bundle is
// traceable back to the exact source tree. CI (GitHub Actions) sets
// GITHUB_SHA; local dev falls back to `git rev-parse --short HEAD`; if
// git is unavailable (shallow clone, sandbox) we ship the literal "dev"
// so the footer line is always present and non-broken.
//
// Wall-clock at build time is operational telemetry (CLAUDE.md section
// 10 carve-out: control-plane artifacts MAY stamp generated_at); this
// is NOT data-row provenance.
function buildSha(): string {
  const ci = process.env.GITHUB_SHA;
  if (ci) return ci.slice(0, 7);
  try {
    return execSync("git rev-parse --short=7 HEAD", {
      cwd: repoRoot,
    })
      .toString()
      .trim();
  } catch {
    return "dev";
  }
}

const BUILD_SHA = buildSha();
const BUILD_DATE = new Date().toISOString().slice(0, 10);

// Build-time icon registry. Walks frontend/public/icons/*.svg, parses each
// file through the strict allowlist parser in
// frontend/src/lib/icons/parse.ts, and exposes the result as the virtual
// module `virtual:icon-registry`. The parser never runs in the browser —
// only the structured `IconRegistry` object reaches the bundle.
//
// The SVG bytes live under frontend/public/icons/ (plan section 21.10,
// party-symbols precedent: static SVG assets are public/, the allowlist +
// parser are code and stay under src/lib/icons/). LICENCES.md sits next
// to the SVGs and is the provenance ledger every shipped icon row needs.
//
// Rejections fail the build LOUDLY with a precise `<file>:<line>:<col>
// <reason>` message. See frontend/src/lib/icons/README.md for the
// contributor-facing contract.
function iconRegistryPlugin() {
  const VIRTUAL_ID = "virtual:icon-registry";
  const RESOLVED_ID = "\0" + VIRTUAL_ID;
  const iconsDir = resolve(fileURLToPath(new URL(".", import.meta.url)), "public", "icons");

  function loadAll(): Record<string, Icon> {
    const out: Record<string, Icon> = {};
    if (!existsSync(iconsDir)) return out;
    const entries = readdirSync(iconsDir, { withFileTypes: true });
    for (const entry of entries) {
      if (!entry.isFile()) continue;
      if (!entry.name.endsWith(".svg")) continue;
      if (entry.name.startsWith("_")) continue;
      const stem = entry.name.slice(0, -4);
      if (!ICON_FILENAME_REGEX.test(stem)) {
        throw new Error(
          `icon filename '${entry.name}' violates ICON_FILENAME_REGEX (kebab-case, no leading digit-only group). See frontend/src/lib/icons/README.md.`
        );
      }
      const src = readFileSync(resolve(iconsDir, entry.name), "utf8");
      // parseIcon throws IconParseError on rejection; the unwrapped message
      // already carries the file:line:col format.
      out[stem] = parseIcon(src, entry.name, stem);
    }
    return out;
  }

  return {
    name: "yen-gov-icon-registry",
    enforce: "pre" as const,
    resolveId(id: string) {
      if (id === VIRTUAL_ID) return RESOLVED_ID;
      return null;
    },
    load(id: string) {
      if (id !== RESOLVED_ID) return null;
      const registry = loadAll();
      // Emit the registry as a frozen object literal. JSON.stringify is
      // safe here because every value is a plain Icon (strings + numbers
      // + arrays + objects) with no functions or undefined holes.
      return `export const iconRegistry = Object.freeze(${JSON.stringify(registry)});`;
    },
    configureServer(server: any) {
      // Hot-reload: when a contributor adds/edits an SVG in dev, invalidate
      // the virtual module so the next import re-parses the folder.
      const handler = (file: string) => {
        if (file.startsWith(iconsDir) && file.endsWith(".svg")) {
          const mod = server.moduleGraph.getModuleById(RESOLVED_ID);
          if (mod) server.moduleGraph.invalidateModule(mod);
        }
      };
      server.watcher.on("add", handler);
      server.watcher.on("change", handler);
      server.watcher.on("unlink", handler);
    },
  };
}

// Templating for the SPA 404.html shim. Vite copies public/* verbatim, so
// %BASE_URL% in 404.html would otherwise survive into the dist output and
// break the redirect on project Pages (where base is e.g. /yen-gov/). This
// plugin substitutes the placeholder during the build's writeBundle phase.
function template404Plugin() {
  return {
    name: "yen-gov-template-404",
    apply: "build" as const,
    writeBundle() {
      const target = resolve(repoRoot, "frontend", "dist", "404.html");
      if (!existsSync(target)) return;
      const html = readFileSync(target, "utf8");
      const replaced = html.replace(/%BASE_URL%/g, BASE_URL);
      writeFileSync(target, replaced, "utf8");
    },
  };
}

export default defineConfig({
  base: BASE_URL,
  define: {
    __BUILD_SHA__: JSON.stringify(BUILD_SHA),
    __BUILD_DATE__: JSON.stringify(BUILD_DATE),
  },
  plugins: [svelte(), serveDatasets(), iconRegistryPlugin(), template404Plugin()],
  // Vite 6's default condition list doesn't always include "browser" for
  // SSR-aware packages (svelte 5's exports map falls back to its server
  // entry without it, which throws lifecycle_function_unavailable on
  // mount). Force the browser condition for both the client graph and the
  // dep optimizer.
  resolve: {
    conditions: ["browser", "module", "import", "default"],
  },
  optimizeDeps: {
    esbuildOptions: {
      conditions: ["browser", "module", "import", "default"],
    },
  },
  server: {
    fs: { allow: [repoRoot] },
  },
  // Vitest config — keep the unit-test runner away from Playwright's
  // e2e/*.spec.ts files (they call test.describe() from @playwright/test,
  // which throws when collected by vitest).
  test: {
    include: ["src/**/*.{test,spec}.{ts,js}"],
    exclude: ["node_modules/**", "dist/**", "e2e/**"],
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    // Split maplibre-gl + pmtiles into their own chunk. They're heavy
    // (~280 KB gzipped) and only needed on routes that mount a map. Routes
    // that don't render a map still incur the cost on first visit because
    // the static import in MapChoropleth.svelte makes maplibre an eager
    // dep of every route module that transitively imports it — but the
    // separate chunk lets the browser cache it independently.
    rollupOptions: {
      output: {
        manualChunks: {
          maplibre: ["maplibre-gl", "pmtiles"],
        },
      },
    },
  },
});
