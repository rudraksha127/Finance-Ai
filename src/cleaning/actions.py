"""Corporate-action backward adjustment — DATA_CLEANING_VALIDATION.md §3.

Implements the approved adjustment strategy for the file-based MVP:

- **Split / Bonus / Reverse split**: multiply historical prices (before
  the effective date) by ``1 / ratio`` — the same backward formula for
  forward and reverse splits (ratio < 1 for reverse). Bonus issue is
  modeled as a split-like ratio (e.g. 1:1 bonus → ratio 2).
- **Dividend**: multiply historical prices before the ex-date by
  ``1 - D / close_day_before_ex_date``.
- **Symbol change**: rename only, no price adjustment (blueprint §3.6).

Raw records are never rewritten: adjustment produces *new cleaned
records* for the interim tier. Only ``open/high/low/close`` are
adjusted; ``volume`` is left untouched (the raw record keeps the
provider's share counts; adjusted-volume conventions are a Phase-2
concern).

Action record keys (subset of DATA_ARCHITECTURE §3.3):

    type: split | bonus | dividend | ticker_change
    ratio: float (split/bonus)  — shares after : before
    dividend_amount: float      — per share (dividend)
    effective_date: ISO date    — split/bonus date, dividend ex-date
    old_symbol / new_symbol     — ticker_change
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src.core.errors import StorageError

PRICE_COLUMNS = ("open", "high", "low", "close")

ACTION_TYPES = frozenset({"split", "bonus", "dividend", "ticker_change"})


@dataclass(frozen=True)
class ActionOutcome:
    """Result of applying one corporate action to a candle batch."""

    action: dict[str, Any]
    rows_affected: int
    factor: float | None  # None for ticker_change


@dataclass(frozen=True)
class AdjustmentSummary:
    """Aggregate of all applied actions (audit + report)."""

    actions_applied: int
    total_rows_adjusted: int
    outcomes: tuple[ActionOutcome, ...] = ()


class CorporateActionError(StorageError):
    """A corporate-action definition is invalid or cannot be applied."""


def load_actions(path: Path | None) -> list[dict[str, Any]]:
    """Load a JSON list of corporate-action records from a file."""
    if path is None or not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise CorporateActionError(f"cannot read corporate actions {path}: {error}") from error
    if not isinstance(payload, list):
        raise CorporateActionError(f"corporate actions {path} must be a JSON list")
    actions = [validate_action(record) for record in payload]
    actions.sort(key=lambda action: action["effective_date"])
    return actions


def validate_action(record: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize one action record (raises CorporateActionError)."""
    action_type = record.get("type")
    if action_type not in ACTION_TYPES:
        raise CorporateActionError(
            f"unsupported corporate action type {action_type!r}; expected one of {sorted(ACTION_TYPES)}"
        )
    raw_effective = record.get("effective_date")
    if isinstance(raw_effective, date):
        effective_date = raw_effective
    else:
        try:
            effective_date = date.fromisoformat(raw_effective)
        except (KeyError, TypeError, ValueError):
            raise CorporateActionError(
                f"action {action_type!r} has invalid effective_date {raw_effective!r}"
            ) from None

    normalized = dict(record)
    normalized["effective_date"] = effective_date

    if action_type in {"split", "bonus"}:
        ratio = float(record.get("ratio", 1.0))
        if ratio <= 0:
            raise CorporateActionError(f"{action_type} action must have ratio > 0, got {ratio}")
        if action_type == "split" and ratio == 1.0:
            raise CorporateActionError("split ratio must differ from 1.0")
        normalized["ratio"] = ratio
    elif action_type == "dividend":
        amount = float(record.get("dividend_amount", 0.0))
        if amount <= 0:
            raise CorporateActionError("dividend action must have dividend_amount > 0")
        normalized["dividend_amount"] = amount
    elif action_type == "ticker_change":
        old_symbol = record.get("old_symbol")
        new_symbol = record.get("new_symbol")
        if not old_symbol or not new_symbol or old_symbol == new_symbol:
            raise CorporateActionError("ticker_change requires distinct old_symbol and new_symbol")
        normalized["old_symbol"] = str(old_symbol).strip().upper()
        normalized["new_symbol"] = str(new_symbol).strip().upper()
    return normalized


def apply_actions(
    records: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], AdjustmentSummary]:
    """Backward-adjust a candle batch for the given actions.

    Rows before ``effective_date`` (for splits/bonus) or before the
    dividend ex-date are adjusted; rows on/after the date are untouched.
    Actions are applied chronologically (blueprint §3.4). Returns new
    records (raw records are never mutated by callers — this function
    copies defensively).
    """
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    records = [dict(record) for record in records]
    outcomes: list[ActionOutcome] = []
    total_adjusted = 0

    for raw_action in actions:
        action = validate_action(raw_action)
        effective = action["effective_date"]
        action_type = action["type"]

        if action_type == "ticker_change":
            # Rename only; no price adjustment (blueprint §3.6).
            old_symbol = action["old_symbol"].upper()
            new_symbol = action["new_symbol"].upper()
            affected = 0
            for record in records:
                if str(record.get("ticker", "")).upper() == old_symbol:
                    record["ticker"] = new_symbol
                    record["ticker_changed"] = True
                    affected += 1
            outcomes.append(ActionOutcome(action=action, rows_affected=affected, factor=None))
            total_adjusted += affected
            continue

        if action_type in {"split", "bonus"}:
            factor = 1.0 / float(action["ratio"])
        else:  # dividend
            close_before = _closing_price_on_or_before(records, effective)
            if close_before is None or close_before <= 0:
                outcomes.append(ActionOutcome(action=action, rows_affected=0, factor=None))
                continue
            factor = 1.0 - float(action["dividend_amount"]) / close_before
            if factor <= 0:
                raise CorporateActionError(
                    f"dividend {action['dividend_amount']} on {effective} exceeds "
                    f"pre-ex close {close_before}; adjustment factor {factor:.3f} is not positive"
                )

        affected = 0
        for record in records:
            if record["timestamp"].date() < effective:
                for column in PRICE_COLUMNS:
                    record[column] = float(record[column]) * factor
                record.setdefault("adjustments", []).append(
                    {"type": action_type, "effective_date": effective.isoformat(), "factor": factor}
                )
                affected += 1
        outcomes.append(ActionOutcome(action=action, rows_affected=affected, factor=factor))
        total_adjusted += affected

    return records, AdjustmentSummary(
        actions_applied=len(outcomes),
        total_rows_adjusted=total_adjusted,
        outcomes=tuple(outcomes),
    )


def _closing_price_on_or_before(records: list[dict[str, Any]], effective: date) -> float | None:
    """Closing price on the last trading row strictly before ``effective``.

    The dividend ex-date is the first date trading *without* the dividend;
    the pre-ex close is therefore the last close before that date
    (blueprint §3.3 "P_close_before_ex_date").
    """
    candidates = [
        float(record["close"])
        for record in records
        if record["timestamp"].date() < effective and record.get("close") is not None
    ]
    return candidates[-1] if candidates else None
