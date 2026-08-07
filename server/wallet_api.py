"""Read-only wallet table API backed by Railway Postgres.

Used by /wallet-api when FRONG_WALLET_DATABASE_URL is set so the site does not
depend on api.frong.ai (Cloudflare Bot Fight / DoH quirks from Railway).
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None  # type: ignore

CHAIN = os.environ.get("FRONG_CHAIN", os.environ.get("CHAIN", "robinhood"))
MAX_PER_PAGE = int(os.environ.get("API_MAX_PER_PAGE", "250"))
MAX_ABS_TOTAL_PROFIT = float(os.environ.get("MAX_ABS_TOTAL_PROFIT", "1000000"))

WALLET_COLUMNS = [
    "address",
    "total_profit",
    "realized_profit_30d",
    "unrealized_profit",
    "all_pnl",
    "winrate_30d",
    "buy_30d",
    "sell_30d",
    "balance",
    "token_num",
    "pnl_2x_5x_num",
    "pnl_gt_5x_num",
    "kol_rank",
    "avg_holding_period",
    "no_buy_hold_ratio",
    "sub_75k_entries",
    "sub_75k_avg_entry",
    "sub_75k_avg_buy_amount",
    "sub_75k_avg_buy_30d",
    "sub_75k_avg_sell_30d",
    "sub_75k_avg_total_profit_pnl",
    "fdv_75k_250k_entries",
    "fdv_75k_250k_avg_entry",
    "fdv_75k_250k_avg_buy_amount",
    "fdv_75k_250k_avg_buy_30d",
    "fdv_75k_250k_avg_sell_30d",
    "fdv_75k_250k_avg_total_profit_pnl",
    "fast_trades_percentage",
    "date_reviewed",
    "updated_at",
]
SORTABLE = set(WALLET_COLUMNS)
NUMERIC_FILTER_COLUMNS = {
    "total_profit",
    "realized_profit_30d",
    "unrealized_profit",
    "all_pnl",
    "winrate_30d",
    "buy_30d",
    "sell_30d",
    "balance",
    "token_num",
    "pnl_2x_5x_num",
    "pnl_gt_5x_num",
    "sub_75k_entries",
    "sub_75k_avg_entry",
    "sub_75k_avg_buy_amount",
    "sub_75k_avg_buy_30d",
    "sub_75k_avg_sell_30d",
    "sub_75k_avg_total_profit_pnl",
    "fdv_75k_250k_entries",
    "fdv_75k_250k_avg_entry",
    "fdv_75k_250k_avg_buy_amount",
    "fdv_75k_250k_avg_buy_30d",
    "fdv_75k_250k_avg_sell_30d",
    "fdv_75k_250k_avg_total_profit_pnl",
    "fast_trades_percentage",
}

router = APIRouter()


def database_url() -> str:
    return (
        os.environ.get("FRONG_WALLET_DATABASE_URL", "").strip()
        or os.environ.get("WALLET_DATABASE_URL", "").strip()
    )


def enabled() -> bool:
    return bool(database_url()) and psycopg is not None


def _connect():
    url = database_url()
    if not url or psycopg is None:
        raise HTTPException(503, "wallet database not configured")
    return psycopg.connect(url, connect_timeout=15)


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _parse_filters(filters: Optional[str]) -> dict[str, dict]:
    if not filters:
        return {}
    try:
        parsed = json.loads(filters)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(400, "filters must be valid JSON") from None
    if not isinstance(parsed, dict):
        raise HTTPException(400, "filters must be a JSON object")
    return parsed


def _select_fields(fields: Optional[str]) -> list[str]:
    if not fields:
        return list(WALLET_COLUMNS)
    selected = [field.strip() for field in fields.split(",") if field.strip()]
    invalid = [field for field in selected if field not in SORTABLE]
    if invalid:
        raise HTTPException(400, f"unknown fields: {invalid}")
    if not selected:
        raise HTTPException(400, "fields must contain at least one column")
    return list(dict.fromkeys(selected))


def _fetch_wallets(
    *,
    page: int,
    per_page: int,
    sort_by: str,
    order: str,
    search: Optional[str] = None,
    fdv_only: bool = False,
    filters: Optional[str] = None,
    fields: Optional[str] = None,
) -> dict:
    if sort_by not in SORTABLE:
        raise HTTPException(400, f"sort_by must be one of {sorted(SORTABLE)}")
    if order.lower() not in {"asc", "desc"}:
        raise HTTPException(400, "order must be asc or desc")
    direction = order.upper()
    selected = _select_fields(fields)

    where = [
        "chain = %(chain)s",
        "(total_profit IS NULL OR ABS(total_profit) <= %(quality_limit)s)",
    ]
    params: dict[str, Any] = {"chain": CHAIN, "quality_limit": MAX_ABS_TOTAL_PROFIT}
    if search:
        where.append("address ILIKE %(search)s")
        params["search"] = f"%{search}%"
    if fdv_only:
        where.append("fdv_checked_at IS NOT NULL")

    parsed_filters = _parse_filters(filters)
    for i, (col, bounds) in enumerate(parsed_filters.items()):
        if col not in NUMERIC_FILTER_COLUMNS or not isinstance(bounds, dict):
            continue
        lo, hi = bounds.get("min"), bounds.get("max")
        if lo is not None:
            key = f"fmin_{i}"
            where.append(f"{col} >= %({key})s")
            params[key] = lo
        if hi is not None:
            key = f"fmax_{i}"
            where.append(f"{col} <= %({key})s")
            params[key] = hi

    where_sql = " AND ".join(where)
    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page
    cols = ", ".join(selected)

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM wallets WHERE {where_sql}", params)
            total = int(cur.fetchone()[0])
            cur.execute(
                f"""
                SELECT {cols} FROM wallets
                WHERE {where_sql}
                ORDER BY {sort_by} {direction} NULLS LAST
                LIMIT %(limit)s OFFSET %(offset)s
                """,
                params,
            )
            rows = [
                {col: _jsonable(val) for col, val in zip(selected, row)}
                for row in cur.fetchall()
            ]

    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": max(1, -(-total // per_page)),
        "wallets": rows,
    }


@router.get("/api/summary")
@router.get("/v1/summary")
def summary() -> dict:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*),
                       COUNT(fdv_checked_at),
                       COUNT(*) FILTER (WHERE total_profit > 0),
                       MAX(updated_at)
                FROM wallets
                WHERE chain = %s
                  AND (total_profit IS NULL OR ABS(total_profit) <= %s)
                """,
                (CHAIN, MAX_ABS_TOTAL_PROFIT),
            )
            total, fdv_checked, profitable, last_update = cur.fetchone()
    return {
        "chain": CHAIN,
        "total_wallets": total,
        "fdv_enriched": fdv_checked,
        "profitable_wallets": profitable,
        "last_update": last_update.isoformat() if last_update else None,
    }


@router.get("/api/wallets")
@router.get("/v1/wallets")
def wallets(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=MAX_PER_PAGE),
    sort_by: str = Query("total_profit"),
    order: str = Query("desc"),
    search: Optional[str] = Query(None, max_length=100),
    fdv_only: bool = Query(False),
    filters: Optional[str] = Query(None),
    fields: Optional[str] = Query(None, max_length=1000),
) -> dict:
    return _fetch_wallets(
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        order=order,
        search=search,
        fdv_only=fdv_only,
        filters=filters,
        fields=fields,
    )


@router.get("/health")
def health() -> dict:
    return {"ok": True, "source": "postgres"}
