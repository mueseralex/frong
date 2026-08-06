import { useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { shortName } from "../utils/axiom.js";

function shortAddr(a) {
  return a.length > 12 ? `${a.slice(0, 6)}…${a.slice(-4)}` : a;
}

export default function FavoritesManager({ flags, onEdit, onUnstar, onExport, onClose }) {
  const [query, setQuery] = useState("");

  const items = useMemo(() => {
    const q = query.trim().toLowerCase();
    return Object.entries(flags)
      .map(([address, fav]) => ({ address, ...fav }))
      .filter((item) => {
        if (!q) return true;
        return (
          item.address.toLowerCase().includes(q) ||
          (item.name || "").toLowerCase().includes(q) ||
          (item.emoji || "").includes(q)
        );
      })
      .sort((a, b) => (a.name || "").localeCompare(b.name || ""));
  }, [flags, query]);

  const count = Object.keys(flags).length;

  return createPortal(
    <div className="modal-backdrop" onClick={onClose}>
      <div className="favorites-modal" onClick={(e) => e.stopPropagation()}>
        <header className="star-modal-head">
          <h2>Favorites{count ? ` (${count})` : ""}</h2>
          <button type="button" className="modal-x" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>

        <p className="export-lead">
          Edit names and emojis, or remove wallets before exporting to Axiom.
        </p>

        {count > 0 && (
          <input
            className="favorites-search"
            placeholder="Search name or address…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
          />
        )}

        {count === 0 ? (
          <div className="export-empty">
            No favorites yet. Click ☆ on a wallet to star it.
          </div>
        ) : items.length === 0 ? (
          <div className="export-empty">No favorites match that search.</div>
        ) : (
          <div className="favorites-list">
            {items.map((item) => (
              <div key={item.address} className="favorites-row">
                <span className="export-emoji">{item.emoji || "⭐"}</span>
                <div className="export-row-main">
                  <strong>{item.name || shortName(item.address)}</strong>
                  <code title={item.address}>{shortAddr(item.address)}</code>
                </div>
                <span className={`export-alert${item.alertsOn !== false ? " on" : ""}`}>
                  {item.alertsOn !== false ? "alerts on" : "alerts off"}
                </span>
                <div className="favorites-row-actions">
                  <button type="button" className="btn" onClick={() => onEdit(item.address)}>
                    Edit
                  </button>
                  <button type="button" className="btn danger" onClick={() => onUnstar(item.address)}>
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        <footer className="star-modal-actions">
          <button type="button" className="btn" onClick={onClose}>
            Close
          </button>
          <div className="star-modal-actions-right">
            <button
              type="button"
              className="btn primary"
              onClick={onExport}
              disabled={count === 0}
            >
              Export for Axiom
            </button>
          </div>
        </footer>
      </div>
    </div>,
    document.body
  );
}
