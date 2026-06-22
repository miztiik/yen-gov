export interface WindowRange {
  readonly start: number;
  readonly end: number;
}

export interface WindowConstraints {
  readonly count: number;
  readonly minSize?: number;
  readonly maxSize?: number;
}

interface NormalizedConstraints {
  readonly count: number;
  readonly minSize: number;
  readonly maxSize: number;
  readonly lastIndex: number;
}

function positiveIntegerOr(value: number | undefined, fallback: number): number {
  if (value === undefined) return fallback;
  if (!Number.isFinite(value)) return fallback;
  return Math.max(1, Math.floor(value));
}

function normalizeConstraints(c: WindowConstraints): NormalizedConstraints {
  const count = Math.max(1, Math.floor(Number.isFinite(c.count) ? c.count : 1));
  const requestedMin = positiveIntegerOr(c.minSize, 1);
  const requestedMax = positiveIntegerOr(c.maxSize, 3);
  const minSize = Math.min(count, requestedMin);
  const maxSize = Math.min(count, Math.max(minSize, requestedMax));
  return Object.freeze({
    count,
    minSize,
    maxSize,
    lastIndex: count - 1,
  });
}

function indexOrZero(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.round(value);
}

function clampIndex(value: number, c: NormalizedConstraints): number {
  return Math.min(c.lastIndex, Math.max(0, indexOrZero(value)));
}

function freezeRange(start: number, end: number): WindowRange {
  return Object.freeze({ start, end });
}

export function windowSize(r: WindowRange): number {
  return Math.max(0, indexOrZero(r.end) - indexOrZero(r.start) + 1);
}

export function defaultWindow(c: WindowConstraints): WindowRange {
  const n = normalizeConstraints(c);
  const size = Math.min(n.count, n.maxSize);
  return freezeRange(n.count - size, n.lastIndex);
}

export function clampWindow(r: WindowRange, c: WindowConstraints): WindowRange {
  const n = normalizeConstraints(c);
  let start = clampIndex(r.start, n);
  let end = clampIndex(r.end, n);

  if (start > end) {
    const tmp = start;
    start = end;
    end = tmp;
  }

  if (end - start + 1 > n.maxSize) {
    end = start + n.maxSize - 1;
    if (end > n.lastIndex) {
      end = n.lastIndex;
      start = end - n.maxSize + 1;
    }
  }

  if (end - start + 1 < n.minSize) {
    end = start + n.minSize - 1;
    if (end > n.lastIndex) {
      end = n.lastIndex;
      start = end - n.minSize + 1;
    }
  }

  return freezeRange(start, end);
}

export function setStart(
  r: WindowRange,
  start: number,
  c: WindowConstraints,
): WindowRange {
  const n = normalizeConstraints(c);
  const safe = clampWindow(r, c);
  const end = safe.end;
  let nextStart = clampIndex(start, n);

  if (nextStart > end) nextStart = end;
  if (end - nextStart + 1 > n.maxSize) nextStart = end - n.maxSize + 1;
  if (end - nextStart + 1 < n.minSize) nextStart = end - n.minSize + 1;

  return clampWindow({ start: nextStart, end }, c);
}

export function setEnd(
  r: WindowRange,
  end: number,
  c: WindowConstraints,
): WindowRange {
  const n = normalizeConstraints(c);
  const safe = clampWindow(r, c);
  const start = safe.start;
  let nextEnd = clampIndex(end, n);

  if (nextEnd < start) nextEnd = start;
  if (nextEnd - start + 1 > n.maxSize) nextEnd = start + n.maxSize - 1;
  if (nextEnd - start + 1 < n.minSize) nextEnd = start + n.minSize - 1;

  return clampWindow({ start, end: nextEnd }, c);
}

export function panTo(
  r: WindowRange,
  newStart: number,
  c: WindowConstraints,
): WindowRange {
  const n = normalizeConstraints(c);
  const safe = clampWindow(r, c);
  const size = windowSize(safe);
  const latestStart = n.count - size;
  const start = Math.min(latestStart, Math.max(0, indexOrZero(newStart)));
  return freezeRange(start, start + size - 1);
}