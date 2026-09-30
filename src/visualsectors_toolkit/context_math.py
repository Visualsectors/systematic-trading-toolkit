"""Pure arithmetic matching preset-skills 0.5.0's released rounding rules."""
from math import floor, isfinite, sqrt


def rounded(value, digits=4):
    if value is None or not isfinite(value):
        return None
    scale = 10 ** digits
    return floor(value * scale + 0.5) / scale


def pct(value):
    return None if value is None else rounded(value * 100, 2)


def mean(values):
    return sum(values) / len(values) if values else None


def median(values):
    if not values:
        return None
    values = sorted(values)
    middle = len(values) // 2
    return values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2


def mad(values):
    centre = median(values)
    return None if centre is None else median([abs(value - centre) for value in values])


def deviation(values):
    if len(values) < 2:
        return None
    centre = mean(values)
    return sqrt(sum((value - centre) ** 2 for value in values) / (len(values) - 1))


def percentile(values, current):
    if len(values) < 5:
        return None
    return (sum(value < current for value in values) + sum(value == current for value in values) * 0.5) / len(values)


def sign(value):
    return (value > 0) - (value < 0)


def bars(series):
    return sorted(series["bars"], key=lambda bar: bar["session"])[-253:]


def period(rows, sessions):
    return rows[-1]["close"] / rows[-sessions - 1]["close"] - 1 if len(rows) > sessions else None


def aligned(series, reference, sessions):
    if len(reference) <= sessions or series is None:
        return None
    closes = {bar["session"]: bar["close"] for bar in bars(series)}
    start, end = closes.get(reference[-sessions - 1]["session"]), closes.get(reference[-1]["session"])
    return None if start is None or end is None else end / start - 1
