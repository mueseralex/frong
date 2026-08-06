// Address is always pinned first and isn't part of the hide/reorder system.
export const ADDRESS_COLUMN = { key: "address", label: "Wallet", type: "address" };

// Everything else — hideable + reorderable, in the shipped default order.
export const DEFAULT_COLUMNS = [
  { key: "total_profit", label: "Total Profit", type: "money" },
  { key: "realized_profit_30d", label: "Realized 30d", type: "money" },
  { key: "unrealized_profit", label: "Unrealized", type: "money" },
  { key: "winrate_30d", label: "Winrate", type: "pct01" },
  { key: "all_pnl", label: "PnL", type: "pct01" },
  { key: "buy_30d", label: "Buys 30d", type: "int" },
  { key: "sell_30d", label: "Sells 30d", type: "int" },
  { key: "balance", label: "Balance", type: "num" },
  { key: "token_num", label: "Tokens", type: "int" },
  { key: "pnl_2x_5x_num", label: "2-5x", type: "int" },
  { key: "pnl_gt_5x_num", label: ">5x", type: "int" },
  { key: "sub_75k_entries", label: "<75k Entries", type: "int" },
  { key: "sub_75k_avg_entry", label: "<75k Avg FDV", type: "money" },
  { key: "sub_75k_avg_buy_amount", label: "<75k Avg Buy $", type: "money" },
  { key: "sub_75k_avg_buy_30d", label: "<75k Buys", type: "num" },
  { key: "sub_75k_avg_sell_30d", label: "<75k Sells", type: "num" },
  { key: "sub_75k_avg_total_profit_pnl", label: "<75k PnL", type: "pct01" },
  { key: "fdv_75k_250k_entries", label: "75-250k Entries", type: "int" },
  { key: "fdv_75k_250k_avg_entry", label: "75-250k Avg FDV", type: "money" },
  { key: "fdv_75k_250k_avg_buy_amount", label: "75-250k Avg Buy $", type: "money" },
  { key: "fdv_75k_250k_avg_buy_30d", label: "75-250k Buys", type: "num" },
  { key: "fdv_75k_250k_avg_sell_30d", label: "75-250k Sells", type: "num" },
  { key: "fdv_75k_250k_avg_total_profit_pnl", label: "75-250k PnL", type: "pct01" },
  { key: "fast_trades_percentage", label: "Fast Trades", type: "pct" },
  { key: "date_reviewed", label: "Reviewed", type: "date" },
];

export const COLUMN_MAP = Object.fromEntries(DEFAULT_COLUMNS.map((c) => [c.key, c]));
export const DEFAULT_ORDER = DEFAULT_COLUMNS.map((c) => c.key);

// Reconciles a stored column order against the current known columns: drops
// keys that no longer exist, appends any new ones the code has added since.
export function normalizeOrder(stored) {
  if (!Array.isArray(stored)) return DEFAULT_ORDER.slice();
  const known = new Set(DEFAULT_ORDER);
  const kept = stored.filter((k) => known.has(k));
  const missing = DEFAULT_ORDER.filter((k) => !kept.includes(k));
  return [...kept, ...missing];
}

export const HIGHLIGHT_COLORS = [
  { key: "lime", css: "#00c805" },
  { key: "amber", css: "#ffc700" },
  { key: "blue", css: "#5aa9ff" },
  { key: "red", css: "#ff5000" },
  { key: "purple", css: "#c792ff" },
];
