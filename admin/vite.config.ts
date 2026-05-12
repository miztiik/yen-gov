// Vite config for the dev-only admin app.
//
// Defaults:
//   - dev server on port 5174 (5173 is the public app — they MUST coexist
//     because the operator typically runs both)
//   - /api proxied to the FastAPI backend on 127.0.0.1:8000
//
// The browser-conditions block mirrors the public app's (frontend/vite.config.ts)
// — Vite 6 + Svelte 5 needs both `resolve.conditions` and the matching
// `optimizeDeps.esbuildOptions.conditions` set to "browser", otherwise the
// SSR entry point of svelte gets picked and `mount()` throws
// `lifecycle_function_unavailable` at runtime.

/// <reference types="vitest" />
import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

export default defineConfig({
  plugins: [svelte()],
  resolve: {
    conditions: ["browser", "module", "import", "default"],
  },
  optimizeDeps: {
    esbuildOptions: {
      conditions: ["browser", "module", "import", "default"],
    },
  },
  server: {
    port: 5174,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: false,
      },
    },
  },
  // Vitest — unit tests live next to the modules they cover.
  // No DOM environment yet (api.ts is a pure fetch wrapper); add `jsdom`
  // here when component tests land.
  test: {
    include: ["src/**/*.{test,spec}.{ts,js}"],
    exclude: ["node_modules/**", "dist/**", "e2e/**"],
  },
});
