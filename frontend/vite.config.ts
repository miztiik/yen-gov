import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { fileURLToPath } from "node:url";
import { resolve, extname, sep } from "node:path";
import { readFileSync, statSync } from "node:fs";

// Repo root = parent of frontend/. Used by both the dev middleware (which
// serves datasets/ in place — per CLAUDE.md §4 the frontend MUST NOT commit
// data files, and per the user's "no copy" choice we don't even copy at
// build time) and by the deploy step (Phase 4) which uploads frontend/dist
// alongside datasets/ to a single Pages root.
const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..");

// Map file extension → Content-Type. Anything not listed defaults to
// application/octet-stream (correct for opaque binaries; sqlite-wasm needs
// this for results.sqlite).
const CONTENT_TYPES: Record<string, string> = {
  ".json": "application/json; charset=utf-8",
  ".sqlite": "application/vnd.sqlite3",
  ".csv": "text/csv; charset=utf-8",
  ".geojson": "application/geo+json; charset=utf-8",
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

export default defineConfig({
  plugins: [svelte(), serveDatasets()],
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
