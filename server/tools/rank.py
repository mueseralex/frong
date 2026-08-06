"""Lightweight batch percentile scorer (Frong trackability rank)."""

from __future__ import annotations

from typing import Any

# Absolute floors — percentile score alone must not greenlight junk wallets.
MIN_TRACK_WINRATE = 35.0
MIN_TRACK_SCORE = 65.0
MIN_TRACK_TRADES = 8  # buy_30d + sell_30d


def _num(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _winrate_pct(raw: Any) -> float:
    """Normalize API winrate to 0–100.

    GMGN / our DB usually store 0–1 fractions. Values above 1 are treated as
    already-percent. Guard the old bug where 1% stored as ``1`` became 100%.
    """
    win = _num(raw)
    if win < 0:
        return 0.0
    if win <= 1.0:
        return round(win * 100.0, 1)
    if win <= 100.0:
        return round(win, 1)
    return 100.0


def _percentile_ranks(values: list[float]) -> list[float]:
    n = len(values)
    if n == 0:
        return []
    if n == 1:
        return [50.0]
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0
        pct = 100.0 * avg / (n - 1)
        for k in range(i, j + 1):
            ranks[order[k]] = pct
        i = j + 1
    return ranks


def compact_wallet(w: dict[str, Any]) -> dict[str, Any]:
    addr = str(w.get("address") or w.get("wallet") or "")
    win_pct = _winrate_pct(w.get("winrate_30d") if w.get("winrate_30d") is not None else w.get("winrate"))
    return {
        "address": addr,
        "prefix": (addr[:6] + "…" + addr[-4:]) if len(addr) >= 12 else addr,
        "total_profit": _num(w.get("total_profit")),
        "realized_profit_30d": _num(w.get("realized_profit_30d")),
        "winrate_30d": win_pct,
        "token_num": int(_num(w.get("token_num"))),
        "buy_30d": int(_num(w.get("buy_30d"))),
        "sell_30d": int(_num(w.get("sell_30d"))),
        "fast_trades_percentage": _num(w.get("fast_trades_percentage")),
        "sub_75k_entries": int(_num(w.get("sub_75k_entries"))),
        "pnl_gt_5x_num": int(_num(w.get("pnl_gt_5x_num"))),
        "status": w.get("status") or "ok",
    }


def _absolute_trackable(r: dict[str, Any]) -> bool:
    trades = r["buy_30d"] + r["sell_30d"]
    return (
        r["winrate_30d"] >= MIN_TRACK_WINRATE
        and r["total_profit"] > 0
        and trades >= MIN_TRACK_TRADES
    )


def _verdict(r: dict[str, Any]) -> str:
    """Hard YES / NO / MAYBE for the model — do not soft-pedal."""
    wr = r["winrate_30d"]
    pnl = r["total_profit"]
    if wr < 25.0 or pnl < 0:
        return "NO"
    if r.get("track"):
        return "YES"
    if wr >= 40.0 and pnl > 0 and (r["buy_30d"] + r["sell_30d"]) >= MIN_TRACK_TRADES:
        return "MAYBE"
    return "NO"


def rank_wallets(wallets: list[dict[str, Any]], top_n: int = 10) -> list[dict[str, Any]]:
    rows = [compact_wallet(w) for w in wallets if (w.get("address") or w.get("wallet"))]
    if not rows:
        return []

    # Single-wallet: skip fake percentiles — use absolute quality only.
    if len(rows) == 1:
        r = rows[0]
        # Map absolute quality into a simple 0–100-ish score for display.
        wr = r["winrate_30d"]
        pnl = max(r["realized_profit_30d"], r["total_profit"])
        score = min(
            100.0,
            0.45 * wr
            + 0.35 * min(100.0, max(0.0, pnl) / 5000.0 * 100.0)
            + 0.20 * min(100.0, (r["buy_30d"] + r["sell_30d"]) / 50.0 * 100.0),
        )
        r["score"] = round(score, 1)
        r["track"] = _absolute_trackable(r) and score >= 55.0
        r["verdict"] = _verdict(r)
        r["rank"] = 1
        return rows

    profit = [
        r["realized_profit_30d"] if r["realized_profit_30d"] else r["total_profit"] for r in rows
    ]
    win = [r["winrate_30d"] for r in rows]
    early = [float(r["sub_75k_entries"]) for r in rows]
    mult = [float(r["pnl_gt_5x_num"]) for r in rows]
    discipline = [-r["fast_trades_percentage"] for r in rows]

    p_profit = _percentile_ranks(profit)
    p_win = _percentile_ranks(win)
    p_early = _percentile_ranks(early)
    p_mult = _percentile_ranks(mult)
    p_disc = _percentile_ranks(discipline)

    for i, r in enumerate(rows):
        score = (
            0.30 * p_profit[i]
            + 0.25 * p_win[i]
            + 0.20 * p_early[i]
            + 0.15 * p_mult[i]
            + 0.10 * p_disc[i]
        )
        r["score"] = round(score, 1)
        # Percentile score AND absolute floors (kills 1% WR "track" nonsense).
        r["track"] = score >= MIN_TRACK_SCORE and _absolute_trackable(r)
        r["verdict"] = _verdict(r)

    rows.sort(key=lambda x: x["score"], reverse=True)
    for i, r in enumerate(rows, start=1):
        r["rank"] = i
    return rows[:top_n] if top_n else rows
