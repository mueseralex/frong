import { useEffect, useRef, useState } from "react";
import { COLUMN_MAP } from "../columns.js";

export default function ColumnMenu({
  order,
  hidden,
  onToggle,
  onShowAll,
  onHideAll,
  flaggedOnly,
  onFlaggedOnlyChange,
  flaggedCount,
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const hiddenCount = hidden.length;
  const visibleCount = order.length - hiddenCount;

  return (
    <div className="col-menu" ref={ref}>
      <button className="btn" onClick={() => setOpen((v) => !v)}>
        Filters{flaggedOnly || hiddenCount ? ` (${visibleCount}/${order.length})` : ""} ▾
      </button>
      {open && (
        <div className="col-menu-pop">
          <div className="col-menu-section">
            <div className="col-menu-section-label">View</div>
            <label className="col-menu-item">
              <input
                type="checkbox"
                checked={!!flaggedOnly}
                onChange={(e) => onFlaggedOnlyChange(e.target.checked)}
              />
              Favorites only{flaggedCount ? ` (${flaggedCount})` : ""}
            </label>
          </div>

          <div className="col-menu-section">
            <div className="col-menu-section-label">Columns</div>
            <div className="col-menu-actions">
              <button onClick={onShowAll}>Show all</button>
              <button onClick={onHideAll}>Hide all</button>
            </div>
            <div className="col-menu-list">
              {order.map((key) => {
                const col = COLUMN_MAP[key];
                if (!col) return null;
                const isHidden = hidden.includes(key);
                return (
                  <label key={key} className="col-menu-item">
                    <input
                      type="checkbox"
                      checked={!isHidden}
                      onChange={() => onToggle(key)}
                    />
                    {col.label}
                  </label>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
