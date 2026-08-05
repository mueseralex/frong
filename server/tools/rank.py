"""Lightweight batch percentile scorer (Frong trackability rank)."""

from __future__ import annotations

from typing import Any


def _num(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


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
    addr = str(w.get("address") or "")
    win = _num(w.get("winrate_30d"))
    # API may store 0-1 or 0-100
    if win <= 1.5:
        win_pct = win * 100.0
    else:
        win_pct = win
    return {
        "address": addr,
        "prefix": (addr[:6] + "…" + addr[-4:]) if len(addr) >= 12 else addr,
        "total_profit": _num(w.get("total_profit")),
        "realized_profit_30d": _num(w.get("realized_profit_30d")),
        "winrate_30d": round(win_pct, 1),
        "token_num": int(_num(w.get("token_num"))),
        "buy_30d": int(_num(w.get("buy_30d"))),
        "sell_30d": int(_num(w.get("sell_30d"))),
        "fast_trades_percentage": _num(w.get("fast_trades_percentage")),
        "sub_75k_entries": int(_num(w.get("sub_75k_entries"))),
        "pnl_gt_5x_num": int(_num(w.get("pnl_gt_5x_num"))),
        "status": w.get("status") or "ok",
    }


def rank_wallets(wallets: list[dict[str, Any]], top_n: int = 10) -> list[dict[str, Any]]:
    rows = [compact_wallet(w) for w in wallets if w.get("address")]
    if not rows:
        return []

    profit = [r["realized_profit_30d"] if r["realized_profit_30d"] else r["total_profit"] for r in rows]
    win = [r["winrate_30d"] for r in rows]
    early = [float(r["sub_75k_entries"]) for r in rows]
    mult = [float(r["pnl_gt_5x_num"]) for r in rows]
    # lower fast-trade % is better discipline
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
        r["track"] = score >= 65.0 and r["total_profit"] > 0

    rows.sort(key=lambda x: x["score"], reverse=True)
    for i, r in enumerate(rows, start=1):
        r["rank"] = i
    return rows[:top_n] if top_n else rows
