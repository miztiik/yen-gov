/**
 * Tier-A unit tests for `last-event-memory.ts` (R2 of the state-event-page
 * redesign plan; J-elevated-15 30-day citizen-memo).
 *
 * vitest runs under node by default in this repo (no jsdom/happy-dom dep).
 * We install a minimal in-memory `localStorage` shim on `globalThis` for
 * the duration of each test so the module's `typeof localStorage` guard
 * sees a Storage-shaped object.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  isLastEventFresh,
  readLastEvent,
  writeLastEvent,
} from "./last-event-memory";

function installLocalStorageShim(): void {
  const store = new Map<string, string>();
  const shim: Storage = {
    get length() {
      return store.size;
    },
    clear() {
      store.clear();
    },
    getItem(key: string): string | null {
      return store.has(key) ? store.get(key)! : null;
    },
    key(index: number): string | null {
      return Array.from(store.keys())[index] ?? null;
    },
    removeItem(key: string): void {
      store.delete(key);
    },
    setItem(key: string, value: string): void {
      store.set(key, String(value));
    },
  };
  // @ts-expect-error - assigning to a usually-readonly global by design.
  globalThis.localStorage = shim;
}

function uninstallLocalStorageShim(): void {
  // @ts-expect-error - removing the test shim
  delete (globalThis as { localStorage?: Storage }).localStorage;
}

beforeEach(() => {
  installLocalStorageShim();
  vi.useRealTimers();
});

afterEach(() => {
  vi.useRealTimers();
  uninstallLocalStorageShim();
});

describe("last-event-memory", () => {
  it("writes then reads the same memory", () => {
    const now = new Date("2026-06-15T10:00:00Z");
    vi.useFakeTimers();
    vi.setSystemTime(now);

    writeLastEvent("maharashtra", "assembly-2024", "assembly");
    const got = readLastEvent("maharashtra");

    expect(got).toEqual({
      event_id: "assembly-2024",
      viewed_at_iso: now.toISOString(),
      body: "assembly",
    });
  });

  it("returns null for an unknown state", () => {
    expect(readLastEvent("unknown-state")).toBeNull();
  });

  it("isolates by state_slug (no cross-state leakage)", () => {
    writeLastEvent("karnataka", "assembly-2023", "assembly");
    writeLastEvent("tamil-nadu", "assembly-2021", "assembly");

    expect(readLastEvent("karnataka")?.event_id).toBe("assembly-2023");
    expect(readLastEvent("tamil-nadu")?.event_id).toBe("assembly-2021");
    expect(readLastEvent("kerala")).toBeNull();
  });

  it("persists the state_slug verbatim in the localStorage key", () => {
    writeLastEvent("jammu-and-kashmir", "assembly-2024", "assembly");

    expect(localStorage.getItem("yen-gov:last-event:jammu-and-kashmir")).toContain(
      "assembly-2024",
    );
  });

  it("returns null when memory is older than the 30-day window", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-15T10:00:00Z"));
    writeLastEvent("maharashtra", "assembly-2024", "assembly");

    // 30 days + 1ms later -> expired
    vi.setSystemTime(new Date(Date.now() + 30 * 86_400_000 + 1));

    expect(readLastEvent("maharashtra")).toBeNull();
  });

  it("returns the memory just inside the 30-day boundary", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-15T10:00:00Z"));
    writeLastEvent("maharashtra", "assembly-2024", "assembly");

    // 29 days, 23h, 59m, 59s later -> still fresh
    vi.setSystemTime(new Date(Date.now() + 30 * 86_400_000 - 1_000));

    expect(readLastEvent("maharashtra")?.event_id).toBe("assembly-2024");
  });

  it("returns null on malformed JSON in storage", () => {
    localStorage.setItem("yen-gov:last-event:maharashtra", "{ not json");

    expect(readLastEvent("maharashtra")).toBeNull();
  });

  it("returns null when required fields are missing", () => {
    localStorage.setItem(
      "yen-gov:last-event:maharashtra",
      JSON.stringify({ event_id: "assembly-2024" }),
    );

    expect(readLastEvent("maharashtra")).toBeNull();
  });

  describe("isLastEventFresh", () => {
    it("returns true for a fresh ISO timestamp", () => {
      const now = new Date("2026-06-15T10:00:00Z");
      vi.useFakeTimers();
      vi.setSystemTime(now);

      expect(isLastEventFresh(now.toISOString())).toBe(true);
    });

    it("returns false for a timestamp outside the window", () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date("2026-06-15T10:00:00Z"));

      const oldTimestamp = new Date(Date.now() - 31 * 86_400_000).toISOString();

      expect(isLastEventFresh(oldTimestamp)).toBe(false);
    });

    it("returns false for an invalid ISO string", () => {
      expect(isLastEventFresh("not-a-date")).toBe(false);
    });
  });
});
