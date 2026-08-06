import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ADDRESS_COLUMN, COLUMN_MAP, HIGHLIGHT_COLORS } from "../columns.js";

function fmtMoney(v) {
  if (v == null) return "—";
  const abs = Math.abs(v);
  let out;
  if (abs >= 1e9) out = `$${(abs / 1e9).toFixed(2)}B`;
  else if (abs >= 1e6) out = `$${(abs / 1e6).toFixed(2)}M`;
  else if (abs >= 1e3) out = `$${(abs / 1e3).toFixed(1)}K`;
  else out = `$${abs.toFixed(0)}`;
  return v < 0 ? `-${out}` : out;
}

export function fmt(value, type) {
  if (value == null || value === "") return "—";
  switch (type) {
    case "money": return fmtMoney(value);
    case "pct01": return `${(value * 100).toFixed(1)}%`;
    case "pct": return `${Number(value).toFixed(1)}%`;
    case "int": return Number(value).toLocaleString();
    case "num": return Number(value).toFixed(2);
    case "date": return String(value);
    default: return String(value);
  }
}

function signClass(value, type) {
  if ((type === "money" || type === "pct01") && typeof value === "number") {
    if (value > 0) return "pos";
    if (value < 0) return "neg";
  }
  return "";
}

function shortAddr(a) {
  return a.length > 12 ? `${a.slice(0, 5)}…${a.slice(-4)}` : a;
}

// Debounces min/max typing locally before committing up to the parent (which
// triggers an API call), so fast typing doesn't fire a request per keystroke.
function RangeFilterFields({ colKey, label, bounds, onChange, onClear }) {
  const [localMin, setLocalMin] = useState(bounds.min ?? "");
  const [localMax, setLocalMax] = useState(bounds.max ?? "");
  const minTimer = useRef(null);
  const maxTimer = useRef(null);

  useEffect(() => setLocalMin(bounds.min ?? ""), [bounds.min]);
  useEffect(() => setLocalMax(bounds.max ?? ""), [bounds.max]);

  const handle = (field, setLocal, timerRef) => (value) => {
    setLocal(value);
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => onChange(colKey, field, value), 350);
  };

  return (
    <>
      <div className="filter-menu-row">
        <div className="filter-menu-field">
          <label>Min {label}</label>
          <input
            className="fm-input"
            type="number"
            placeholder="0"
            value={localMin}
            onChange={(e) => handle("min", setLocalMin, minTimer)(e.target.value)}
            autoFocus
          />
        </div>
        <div className="filter-menu-field">
          <label>Max {label}</label>
          <input
            className="fm-input"
            type="number"
            placeholder="∞"
            value={localMax}
            onChange={(e) => handle("max", setLocalMax, maxTimer)(e.target.value)}
          />
        </div>
      </div>
      <button className="fm-clear" onClick={() => onClear(colKey)} disabled={!localMin && !localMax}>
        clear filter
      </button>
    </>
  );
}

export default function WalletTable({
  rows,
  loading,
  sortBy,
  order,
  onSort,
  columns,
  reorderMode,
  onReorder,
  flags,
  onStar,
  highlights,
  onSetHighlight,
  searchInput,
  onSearchChange,
  colFilters,
  onColFilterChange,
  onClearColFilter,
  fdvOnly,
  onFdvOnlyChange,
  flaggedOnly,
  onFlaggedOnlyChange,
  flaggedCount,
}) {
  const [dragKey, setDragKey] = useState(null);
  const [overKey, setOverKey] = useState(null);
  const [swatchTarget, setSwatchTarget] = useState(null); // { address, rect } | null
  const [filterTarget, setFilterTarget] = useState(null); // { key, rect } | null
  const wrapRef = useRef(null);
  const tableRef = useRef(null);
  const [scrollMetrics, setScrollMetrics] = useState({
    left: 0,
    clientWidth: 0,
    scrollWidth: 0,
  });
  const colSpan = columns.length + 2;

  // macOS overlay scrollbars disappear and become almost impossible to grab
  // on a very wide table. Keep a permanently visible scrollbar below the
  // table, synchronized with the real scroll container.
  useEffect(() => {
    const el = wrapRef.current;
    const table = tableRef.current;
    if (!el || !table) return;

    const update = () => {
      setScrollMetrics({
        left: el.scrollLeft,
        clientWidth: el.clientWidth,
        scrollWidth: el.scrollWidth,
      });
    };

    update();
    el.addEventListener("scroll", update, { passive: true });
    const observer = new ResizeObserver(update);
    observer.observe(el);
    observer.observe(table);
    return () => {
      el.removeEventListener("scroll", update);
      observer.disconnect();
    };
  }, [columns, rows]);

  const startHorizontalDrag = (e) => {
    const el = wrapRef.current;
    if (!el || scrollMetrics.scrollWidth <= scrollMetrics.clientWidth) return;

    e.preventDefault();
    const track = e.currentTarget;
    const rect = track.getBoundingClientRect();
    const thumbWidth = Math.max(
      56,
      (scrollMetrics.clientWidth / scrollMetrics.scrollWidth) * rect.width
    );
    const maxThumbLeft = Math.max(1, rect.width - thumbWidth);
    const maxScroll = scrollMetrics.scrollWidth - scrollMetrics.clientWidth;

    if (!e.target.closest(".h-scrollbar-thumb")) {
      const targetLeft = Math.max(
        0,
        Math.min(maxThumbLeft, e.clientX - rect.left - thumbWidth / 2)
      );
      el.scrollLeft = (targetLeft / maxThumbLeft) * maxScroll;
    }

    const startX = e.clientX;
    const startScroll = el.scrollLeft;
    const scrollPerPixel = maxScroll / maxThumbLeft;
    const move = (moveEvent) => {
      el.scrollLeft = startScroll + (moveEvent.clientX - startX) * scrollPerPixel;
    };
    const stop = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      document.body.classList.remove("dragging-h-scrollbar");
    };

    document.body.classList.add("dragging-h-scrollbar");
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop, { once: true });
  };

  // Popovers are portalled to <body> so they can't get clipped by the table's
  // scroll container. Close them if the table scrolls out from under them,
  // or the user clicks elsewhere.
  useEffect(() => {
    if (!swatchTarget && !filterTarget) return;
    const closeOnScroll = () => { setSwatchTarget(null); setFilterTarget(null); };
    const closeOnClick = (e) => {
      if (e.target.closest(".swatch-pop") || e.target.closest(".swatch-toggle")) return;
      if (e.target.closest(".col-filter-pop") || e.target.closest(".filter-dot")) return;
      setSwatchTarget(null);
      setFilterTarget(null);
    };
    const el = wrapRef.current;
    el?.addEventListener("scroll", closeOnScroll, { passive: true });
    document.addEventListener("mousedown", closeOnClick);
    return () => {
      el?.removeEventListener("scroll", closeOnScroll);
      document.removeEventListener("mousedown", closeOnClick);
    };
  }, [swatchTarget, filterTarget]);

  const headerProps = (col) => {
    if (!reorderMode) return {};
    return {
      draggable: true,
      onDragStart: () => setDragKey(col.key),
      onDragOver: (e) => { e.preventDefault(); setOverKey(col.key); },
      onDragLeave: () => setOverKey((k) => (k === col.key ? null : k)),
      onDrop: (e) => {
        e.preventDefault();
        if (dragKey && dragKey !== col.key) onReorder(dragKey, col.key);
        setDragKey(null);
        setOverKey(null);
      },
      onDragEnd: () => { setDragKey(null); setOverKey(null); },
    };
  };

  const openFilter = (key) => (e) => {
    e.stopPropagation();
    const rect = e.currentTarget.getBoundingClientRect();
    setFilterTarget((t) => (t?.key === key ? null : { key, rect }));
  };

  const isFilterActive = (key) => {
    if (key === "mark") return fdvOnly || flaggedOnly;
    if (key === "address") return !!searchInput;
    const f = colFilters[key];
    return !!(f && ((f.min ?? "") !== "" || (f.max ?? "") !== ""));
  };

  const FilterDot = ({ colKey }) => (
    <button
      className={`filter-dot${isFilterActive(colKey) ? " active" : ""}`}
      title="Filter this column"
      onClick={openFilter(colKey)}
    />
  );

  const hasHorizontalOverflow = scrollMetrics.scrollWidth > scrollMetrics.clientWidth + 1;
  const thumbWidthPct = hasHorizontalOverflow
    ? (scrollMetrics.clientWidth / scrollMetrics.scrollWidth) * 100
    : 100;
  const thumbLeftPct = hasHorizontalOverflow
    ? (scrollMetrics.left / scrollMetrics.scrollWidth) * 100
    : 0;

  return (
    <div className="table-region">
      <div ref={wrapRef} className={`table-wrap${loading ? " is-loading" : ""}${reorderMode ? " reorder-mode" : ""}`}>
      <table ref={tableRef}>
        <thead>
          <tr>
            <th className="pin mark-col">
              <FilterDot colKey="mark" />
              Mark
            </th>
            <th
              className={`pin addr-col${sortBy === "address" ? " sorted" : ""}`}
              onClick={() => onSort("address")}
            >
              <FilterDot colKey="address" />
              {ADDRESS_COLUMN.label}
              {sortBy === "address" && <span className="sort-arrow">{order === "desc" ? "▼" : "▲"}</span>}
            </th>
            {columns.map((col) => (
              <th
                key={col.key}
                onClick={() => onSort(col.key)}
                className={[
                  sortBy === col.key ? "sorted" : "",
                  dragKey === col.key ? "dragging" : "",
                  overKey === col.key && dragKey && dragKey !== col.key ? "drag-over" : "",
                ].join(" ").trim()}
                {...headerProps(col)}
              >
                {reorderMode && <span className="grip">⠿</span>}
                {col.type !== "date" && <FilterDot colKey={col.key} />}
                {col.label}
                {sortBy === col.key && (
                  <span className="sort-arrow">{order === "desc" ? "▼" : "▲"}</span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && !loading ? (
            <tr>
              <td className="empty" colSpan={colSpan}>
                No wallets yet — the scraper may still be warming up.
              </td>
            </tr>
          ) : (
            rows.map((row) => {
              const hl = highlights[row.address];
              const fav = flags[row.address];
              const flagged = !!fav;
              return (
                <tr key={row.address} className={hl ? `hl-${hl}` : ""}>
                  <td className="pin mark-col">
                    <div className="mark-cell">
                      <button
                        className={`flag-btn${flagged ? " on" : ""}`}
                        title={flagged ? `${fav.emoji || "⭐"} ${fav.name} — edit favorite` : "Star wallet for Axiom export"}
                        onClick={() => onStar(row.address)}
                      >
                        {flagged ? (fav.emoji || "★") : "☆"}
                      </button>
                      <button
                        className={`swatch-toggle${hl ? " has-hl" : ""}`}
                        style={hl ? { "--sw": HIGHLIGHT_COLORS.find((c) => c.key === hl)?.css } : undefined}
                        title="Highlight row"
                        onClick={(e) => {
                          const rect = e.currentTarget.getBoundingClientRect();
                          setSwatchTarget((t) => (t?.address === row.address ? null : { address: row.address, rect }));
                        }}
                      >
                        ●
                      </button>
                    </div>
                  </td>
                  <td className="pin addr-col addr">
                    <div className="addr-cell">
                      <span className="addr-text" title={row.address}>
                        {shortAddr(row.address)}
                      </span>
                      <button
                        className="copy"
                        type="button"
                        title="Copy address"
                        onClick={() => navigator.clipboard.writeText(row.address)}
                      >
                        ⧉
                      </button>
                    </div>
                  </td>
                  {columns.map((col) => (
                    <td key={col.key} className={signClass(row[col.key], col.type)}>
                      {fmt(row[col.key], col.type)}
                    </td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
      </table>

      {swatchTarget &&
        createPortal(
          <div
            className="swatch-pop"
            style={{ top: swatchTarget.rect.bottom + 6, left: Math.max(8, swatchTarget.rect.left) }}
          >
            {HIGHLIGHT_COLORS.map((c) => (
              <button
                key={c.key}
                className={`swatch${highlights[swatchTarget.address] === c.key ? " active" : ""}`}
                style={{ "--sw": c.css }}
                title={c.key}
                onClick={() => {
                  onSetHighlight(swatchTarget.address, highlights[swatchTarget.address] === c.key ? null : c.key);
                  setSwatchTarget(null);
                }}
              />
            ))}
            <button
              className="swatch clear"
              title="Clear"
              onClick={() => {
                onSetHighlight(swatchTarget.address, null);
                setSwatchTarget(null);
              }}
            >
              ✕
            </button>
          </div>,
          document.body
        )}

      {filterTarget &&
        createPortal(
          <div
            className="col-filter-pop"
            style={{ top: filterTarget.rect.bottom + 6, left: Math.max(8, filterTarget.rect.left - 6) }}
          >
            {filterTarget.key === "mark" && (
              <>
                <label className="toggle fm-toggle">
                  <input type="checkbox" checked={flaggedOnly} onChange={(e) => onFlaggedOnlyChange(e.target.checked)} />
                  Favorites only{flaggedCount ? ` (${flaggedCount})` : ""}
                </label>
                <label className="toggle fm-toggle">
                  <input type="checkbox" checked={fdvOnly} onChange={(e) => onFdvOnlyChange(e.target.checked)} />
                  FDV-enriched only
                </label>
              </>
            )}
            {filterTarget.key === "address" && (
              <div className="filter-menu-field">
                <label>Wallet address</label>
                <input
                  className="fm-input"
                  placeholder="search wallet address…"
                  value={searchInput}
                  onChange={(e) => onSearchChange(e.target.value)}
                  autoFocus
                />
              </div>
            )}
            {filterTarget.key !== "mark" && filterTarget.key !== "address" && (
              <RangeFilterFields
                colKey={filterTarget.key}
                label={COLUMN_MAP[filterTarget.key]?.label ?? ""}
                bounds={colFilters[filterTarget.key] || {}}
                onChange={onColFilterChange}
                onClear={onClearColFilter}
              />
            )}
          </div>,
          document.body
        )}
      </div>
      <div
        className={`h-scrollbar${hasHorizontalOverflow ? "" : " disabled"}`}
        onPointerDown={startHorizontalDrag}
        aria-label="Scroll table horizontally"
        role="scrollbar"
        aria-orientation="horizontal"
        aria-valuemin={0}
        aria-valuemax={Math.max(0, scrollMetrics.scrollWidth - scrollMetrics.clientWidth)}
        aria-valuenow={Math.round(scrollMetrics.left)}
      >
        <div
          className="h-scrollbar-thumb"
          style={{ width: `${thumbWidthPct}%`, marginLeft: `${thumbLeftPct}%` }}
        />
      </div>
    </div>
  );
}

export { COLUMN_MAP };
