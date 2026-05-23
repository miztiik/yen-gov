import { describe, expect, it } from "vitest";

// Pure helper from the brush component module-script. Lives in
// `TemporalViewportBrush.svelte` so it can stay co-located with the
// `<button>{presetLabel(p, recent_count)}</button>` call site, but
// is module-scoped so this vitest can import it (without booting a
// jsdom environment — vitest is node-env per IndicatorChoropleth
// precedent).
import { presetLabel } from "./TemporalViewportBrush.svelte";

describe("TemporalViewportBrush > presetLabel", () => {
  it("renders all five closed-enum presets", () => {
    expect(presetLabel("all", 5)).toBe("All");
    expect(presetLabel("recent", 5)).toBe("Recent 5");
    expect(presetLabel("5y", 5)).toBe("5y");
    expect(presetLabel("10y", 5)).toBe("10y");
    expect(presetLabel("25y", 5)).toBe("25y");
  });

  it("recent label reflects the recent_count override", () => {
    expect(presetLabel("recent", 3)).toBe("Recent 3");
    expect(presetLabel("recent", 10)).toBe("Recent 10");
  });

  it("year-derivable presets ignore recent_count", () => {
    // recent_count is only consumed by the `recent` branch — guard so
    // a future maintainer doesn't accidentally compose it into the
    // year-derivable labels (which would mislead citizens about the
    // window size).
    expect(presetLabel("5y", 99)).toBe("5y");
    expect(presetLabel("10y", 99)).toBe("10y");
    expect(presetLabel("25y", 99)).toBe("25y");
  });
});
