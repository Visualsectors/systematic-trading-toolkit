export function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}

export function mean(values: readonly number[]): number | null {
  return values.length === 0 ? null : values.reduce((sum, value) => sum + value, 0) / values.length;
}

export function median(values: readonly number[]): number | null {
  if (values.length === 0) return null;
  const ordered = [...values].sort((left, right) => left - right);
  const middle = Math.floor(ordered.length / 2);
  const centre = ordered[middle];
  if (centre === undefined) return null;
  return ordered.length % 2 === 1 ? centre : ((ordered[middle - 1] ?? centre) + centre) / 2;
}

export function medianAbsoluteDeviation(values: readonly number[]): number | null {
  const centre = median(values);
  return centre === null ? null : median(values.map((value) => Math.abs(value - centre)));
}

export function standardDeviation(values: readonly number[]): number | null {
  if (values.length < 2) return null;
  const average = mean(values);
  if (average === null) return null;
  return Math.sqrt(values.reduce((sum, value) => sum + (value - average) ** 2, 0) / (values.length - 1));
}

export function percentileRank(values: readonly number[], current: number): number | null {
  if (values.length < 5) return null;
  const below = values.filter((value) => value < current).length;
  const equal = values.filter((value) => value === current).length;
  return (below + equal * 0.5) / values.length;
}

export function round(value: number | null, digits = 4): number | null {
  if (value === null || !Number.isFinite(value)) return null;
  const scale = 10 ** digits;
  return Math.round(value * scale) / scale;
}

export function pct(value: number | null): number | null {
  return value === null ? null : round(value * 100, 2);
}
