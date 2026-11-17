"""TVL aggregation rules for the research pipeline.

The ``tvl`` table stores one row per chain **plus** a ``TOTAL`` row for the same
day. Two mistakes are easy to make and both happened on 2026-11-16:

* summing every row double-counts, because ``TOTAL`` already contains the chains;
* when the ``TOTAL`` row is missing for the newest day, a naive sum silently
  reports a number that is roughly half the real one.

This module makes the choice explicit and returns the provenance with the value,
so a report can say which series it used instead of guessing.
"""
from __future__ import annotations

from dataclasses import dataclass

TOTAL = 'TOTAL'


@dataclass(frozen=True)
class TvlPoint:
    date: str
    value: float
    source: str          # 'total' or 'chains'
    partial: bool        # True when TOTAL was missing and chains were summed
    chains: int


def _rows_by_date(rows):
    """Group (date, chain, value) rows, keeping the last TOTAL per date."""
    grouped: dict[str, dict[str, float]] = {}
    for date, chain, value in rows:
        if value is None:
            continue
        grouped.setdefault(str(date), {})[str(chain)] = float(value)
    return grouped


def aggregate(rows) -> list[TvlPoint]:
    """One point per date, preferring the TOTAL row.

    Duplicate TOTAL rows for a date collapse to the last one seen (the table is
    upserted, but a manual import can leave two). A date with no TOTAL falls back
    to the sum of its chains and is marked ``partial``.
    """
    out: list[TvlPoint] = []
    for date in sorted(_rows_by_date(rows)):
        chains = _rows_by_date(rows)[date]
        if TOTAL in chains:
            out.append(TvlPoint(date, chains[TOTAL], 'total', False,
                                len(chains) - 1))
        else:
            value = sum(v for k, v in chains.items() if k != TOTAL)
            out.append(TvlPoint(date, value, 'chains', True, len(chains)))
    return out


def latest(rows) -> TvlPoint | None:
    points = aggregate(rows)
    return points[-1] if points else None


def latest_complete(points: list[TvlPoint]) -> TvlPoint | None:
    """Newest point that carries a real TOTAL row.

    A chain-only day is a partial snapshot, not a total: publishing its sum as
    the headline TVL understates the market by roughly half. The headline must
    therefore come from the newest complete day, while the partial day is
    reported separately as a data gap.
    """
    for point in reversed(points):
        if not point.partial:
            return point
    return None


def change_pct(points: list[TvlPoint], days: int,
               end: TvlPoint | None = None) -> float | None:
    """Percent change against the closest point at least ``days`` earlier.

    ``end`` defaults to the newest point. Pass the headline point explicitly
    when the newest day is partial, otherwise the comparison is refused even
    though a complete day exists.
    """
    if len(points) < 2:
        return None
    last = end or points[-1]
    if last.partial:
        # comparing a chain-only partial sum against complete TOTAL days would
        # manufacture a crash (68B vs 72B looked like -13% on 2026-11-16)
        return None
    target = _shift_date(last.date, -days)
    earlier = [p for p in points if p.date <= target]
    if not earlier:
        return None
    base = earlier[-1]
    if not base.value:
        return None
    return (last.value - base.value) / base.value * 100.0


def _shift_date(iso: str, days: int) -> str:
    import datetime
    d = datetime.date.fromisoformat(iso) + datetime.timedelta(days=days)
    return d.isoformat()


def date_mismatch(a: str | None, b: str | None) -> bool:
    """True when two series quoted in one sentence do not share a date."""
    return bool(a) and bool(b) and str(a) != str(b)
