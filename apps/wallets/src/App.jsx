import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchWallets, fetchSummary } from "./api.js";
import WalletTable, { fmt } from "./components/WalletTable.jsx";
import ColumnMenu from "./components/ColumnMenu.jsx";
import StarModal from "./components/StarModal.jsx";
import ExportFavorites from "./components/ExportFavorites.jsx";
import FavoritesManager from "./components/FavoritesManager.jsx";
import { useLocalStorage } from "./hooks/useLocalStorage.js";
import { COLUMN_MAP, DEFAULT_ORDER, normalizeOrder } from "./columns.js";
import { downloadCsv } from "./utils/csv.js";
import { migrateFlags, toFavorite } from "./utils/axiom.js";
import FrongNav from "./nav.jsx";

const PER_PAGE_OPTIONS = [25, 50, 100, 250];
const EXPORT_CAP = 5000;

function timeAgo(iso) {
  if (!iso) return "—";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${Math.round(s)}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}

// Range-filter values are entered/stored in display units (e.g. "50" for 50%).
// pct01 columns store a 0-1 fraction in the DB, so convert on the way out.
function toApiFilters(colFilters) {
  const out = {};
  for (const [key, bounds] of Object.entries(colFilters)) {
    if (!bounds) continue;
    const { min, max } = bounds;
    if ((min === "" || min == null) && (max === "" || max == null)) continue;
    const div = COLUMN_MAP[key]?.type === "pct01" ? 100 : 1;
    const entry = {};
    if (min !== "" && min != null) entry.min = Number(min) / div;
    if (max !== "" && max != null) entry.max = Number(max) / div;
    if (Object.keys(entry).length) out[key] = entry;
  }
  return out;
}

export default function App() {
  const [summary, setSummary] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useLocalStorage("hw_per_page", 50);
  const [sortBy, setSortBy] = useLocalStorage("hw_sort_by", "total_profit");
  const [order, setOrder] = useLocalStorage("hw_sort_order", "desc");
  const [search, setSearch] = useState("");
  const [fdvOnly, setFdvOnly] = useLocalStorage("hw_fdv_only", false);
  const [colFilters, setColFilters] = useLocalStorage("hw_col_filters", {});

  // ---- view customization (persisted per-browser) ----
  const [columnOrderRaw, setColumnOrder] = useLocalStorage("hw_column_order", DEFAULT_ORDER);
  const columnOrder = useMemo(() => normalizeOrder(columnOrderRaw), [columnOrderRaw]);
  const [hiddenKeys, setHiddenKeys] = useLocalStorage("hw_hidden_columns", []);
  const [reorderMode, setReorderMode] = useState(false);
  const [flagsRaw, setFlagsRaw] = useLocalStorage("hw_flags", {});
  const flags = useMemo(() => migrateFlags(flagsRaw), [flagsRaw]);
  const [highlights, setHighlights] = useLocalStorage("hw_highlights", {});
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [starTarget, setStarTarget] = useState(null); // address | null
  const [showExportFavorites, setShowExportFavorites] = useState(false);
  const [showFavoritesManager, setShowFavoritesManager] = useState(false);
  const [returnToFavorites, setReturnToFavorites] = useState(false);

  // One-time migration of legacy boolean flags into favorite objects.
  useEffect(() => {
    const migrated = migrateFlags(flagsRaw);
    const needsWrite = Object.keys(flagsRaw).some((addr) => typeof flagsRaw[addr] !== "object");
    if (needsWrite) setFlagsRaw(migrated);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const visibleColumns = useMemo(
    () => columnOrder.filter((k) => !hiddenKeys.includes(k) && COLUMN_MAP[k]).map((k) => COLUMN_MAP[k]),
    [columnOrder, hiddenKeys]
  );

  const searchTimer = useRef(null);
  const [searchInput, setSearchInput] = useState("");
  const apiFilters = useMemo(() => toApiFilters(colFilters), [colFilters]);
  const filtersParam = useMemo(
    () => (Object.keys(apiFilters).length ? JSON.stringify(apiFilters) : ""),
    [apiFilters]
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchWallets({
        page,
        per_page: perPage,
        sort_by: sortBy,
        order,
        search,
        fdv_only: fdvOnly,
        filters: filtersParam,
      });
      setData(res);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [page, perPage, sortBy, order, search, fdvOnly, filtersParam]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    fetchSummary().then(setSummary).catch(() => {});
    const id = setInterval(() => fetchSummary().then(setSummary).catch(() => {}), 60_000);
    return () => clearInterval(id);
  }, []);

  const onSearchChange = (value) => {
    setSearchInput(value);
    clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      setPage(1);
      setSearch(value.trim());
    }, 350);
  };

  const onSort = (col) => {
    setPage(1);
    if (col === sortBy) {
      setOrder(order === "desc" ? "asc" : "desc");
    } else {
      setSortBy(col);
      setOrder("desc");
    }
  };

  const onReorder = (dragKey, targetKey) => {
    setColumnOrder((prev) => {
      const arr = normalizeOrder(prev).filter((k) => k !== dragKey);
      const idx = arr.indexOf(targetKey);
      arr.splice(idx, 0, dragKey);
      return arr;
    });
  };

  const toggleColumn = (key) => {
    setHiddenKeys((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));
  };

  const resetView = () => {
    setColumnOrder(DEFAULT_ORDER);
    setHiddenKeys([]);
    setReorderMode(false);
    setSortBy("total_profit");
    setOrder("desc");
    setPage(1);
  };

  const openStar = (address, fromManager = false) => {
    setReturnToFavorites(!!fromManager);
    setStarTarget(address);
  };

  const closeStarModal = () => {
    setStarTarget(null);
    if (returnToFavorites) {
      setReturnToFavorites(false);
      setShowFavoritesManager(true);
    }
  };

  const saveStar = (address, fields) => {
    setFlagsRaw((prev) => ({
      ...migrateFlags(prev),
      [address]: toFavorite(address, fields),
    }));
    closeStarModal();
  };

  const unstar = (address) => {
    setFlagsRaw((prev) => {
      const next = { ...migrateFlags(prev) };
      delete next[address];
      return next;
    });
    setStarTarget(null);
    // Stay in the manager when removing from there; only bounce back after edit modal.
    if (returnToFavorites) {
      setReturnToFavorites(false);
      setShowFavoritesManager(true);
    }
  };

  const setHighlight = (address, colorKey) => {
    setHighlights((prev) => {
      const next = { ...prev };
      if (colorKey) next[address] = colorKey;
      else delete next[address];
      return next;
    });
  };

  const onColFilterChange = (key, field, value) => {
    setPage(1);
    setColFilters((prev) => ({
      ...prev,
      [key]: { min: "", max: "", ...(prev[key] || {}), [field]: value },
    }));
  };

  const clearColFilter = (key) => {
    setPage(1);
    setColFilters((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const onFdvOnlyChange = (v) => { setPage(1); setFdvOnly(v); };

  const flaggedCount = Object.keys(flags).length;

  const rows = useMemo(() => {
    const base = data?.wallets ?? [];
    return flaggedOnly ? base.filter((r) => flags[r.address]) : base;
  }, [data, flaggedOnly, flags]);

  const exportCsv = async () => {
    setExporting(true);
    try {
      const cols = [{ key: "address", label: "Wallet" }, ...visibleColumns];
      const collected = [];
      let p = 1;
      const cap = 250;
      while (collected.length < EXPORT_CAP) {
        const res = await fetchWallets({
          page: p,
          per_page: cap,
          sort_by: sortBy,
          order,
          search,
          fdv_only: fdvOnly,
          filters: filtersParam,
        });
        collected.push(...res.wallets);
        if (p >= res.pages) break;
        p += 1;
      }
      const finalRows = flaggedOnly ? collected.filter((r) => flags[r.address]) : collected;
      const csvRows = finalRows.map((r) => {
        const out = { address: r.address };
        for (const c of visibleColumns) out[c.key] = fmt(r[c.key], c.type);
        return out;
      });
      downloadCsv(`frong.ai_${Date.now()}.csv`, cols, csvRows);
    } catch (e) {
      setError(e.message);
    } finally {
      setExporting(false);
    }
  };

  const pages = data?.pages ?? 1;

  return (
    <div className="app">
      <FrongNav active="database" />
      {summary && (
        <div className="stats-bar">
          <div className="stat">
            <span className="stat-value">{summary.total_wallets?.toLocaleString()}</span>
            <span className="stat-label">Wallets</span>
          </div>
          <div className="stat">
            <span className="stat-value live"><span className="live-dot" />{timeAgo(summary.last_update)}</span>
            <span className="stat-label">Last update</span>
          </div>
        </div>
      )}

      <div className="toolbar">
        <ColumnMenu
          order={columnOrder}
          hidden={hiddenKeys}
          onToggle={toggleColumn}
          onShowAll={() => setHiddenKeys([])}
          onHideAll={() => setHiddenKeys(columnOrder.slice())}
          flaggedOnly={flaggedOnly}
          onFlaggedOnlyChange={setFlaggedOnly}
          flaggedCount={flaggedCount}
        />
        <button
          className={`btn${reorderMode ? " active" : ""}`}
          onClick={() => setReorderMode((v) => !v)}
          title="Drag column headers to reorder them"
        >
          {reorderMode ? "✓ Reordering — drag headers" : "Reorder columns"}
        </button>
        <button
          className={`btn${flaggedCount ? " active" : ""}`}
          onClick={() => setShowFavoritesManager(true)}
          title="View and edit starred wallets"
        >
          Favorites{flaggedCount ? ` (${flaggedCount})` : ""}
        </button>
        <button className="btn" onClick={exportCsv} disabled={exporting}>
          {exporting ? "Exporting…" : "Export CSV"}
        </button>
        <button
          className="btn primary"
          onClick={() => setShowExportFavorites(true)}
          title="Export starred wallets as Axiom Trade JSON"
        >
          Export favorites{flaggedCount ? ` (${flaggedCount})` : ""}
        </button>
        <button className="btn" onClick={resetView}>Reset view</button>
        <span className="toolbar-hint">Tip: click the ● next to a column name to filter it</span>
      </div>

      {error ? (
        <div className="notice error">API error: {error} — is the public API up?</div>
      ) : (
        <WalletTable
          rows={rows}
          loading={loading}
          sortBy={sortBy}
          order={order}
          onSort={onSort}
          columns={visibleColumns}
          reorderMode={reorderMode}
          onReorder={onReorder}
          flags={flags}
          onStar={openStar}
          highlights={highlights}
          onSetHighlight={setHighlight}
          searchInput={searchInput}
          onSearchChange={onSearchChange}
          colFilters={colFilters}
          onColFilterChange={onColFilterChange}
          onClearColFilter={clearColFilter}
          fdvOnly={fdvOnly}
          onFdvOnlyChange={onFdvOnlyChange}
          flaggedOnly={flaggedOnly}
          onFlaggedOnlyChange={setFlaggedOnly}
          flaggedCount={flaggedCount}
        />
      )}

      {starTarget && (
        <StarModal
          address={starTarget}
          initial={flags[starTarget] || null}
          onSave={(fields) => saveStar(starTarget, fields)}
          onUnstar={() => unstar(starTarget)}
          onClose={closeStarModal}
        />
      )}

      {showFavoritesManager && (
        <FavoritesManager
          flags={flags}
          onEdit={(address) => {
            setShowFavoritesManager(false);
            openStar(address, true);
          }}
          onUnstar={unstar}
          onExport={() => {
            setShowFavoritesManager(false);
            setShowExportFavorites(true);
          }}
          onClose={() => setShowFavoritesManager(false)}
        />
      )}

      {showExportFavorites && (
        <ExportFavorites
          flags={flags}
          highlights={highlights}
          onClose={() => setShowExportFavorites(false)}
        />
      )}

      <footer className="pager">
        <div className="pager-nav">
          <button disabled={page <= 1} onClick={() => setPage(1)}>«</button>
          <button disabled={page <= 1} onClick={() => setPage(page - 1)}>‹</button>
          <span className="pager-info">
            Page {page} of {pages}{data ? ` · ${data.total.toLocaleString()} wallets` : ""}
          </span>
          <button disabled={page >= pages} onClick={() => setPage(page + 1)}>›</button>
          <button disabled={page >= pages} onClick={() => setPage(pages)}>»</button>
        </div>
        <select
          className="per-page"
          value={perPage}
          onChange={(e) => { setPage(1); setPerPage(Number(e.target.value)); }}
        >
          {PER_PAGE_OPTIONS.map((n) => (
            <option key={n} value={n}>{n} / page</option>
          ))}
        </select>
      </footer>
    </div>
  );
}
