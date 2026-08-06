import { useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { copyJson, downloadJson, shortName, toAxiomExport, toFavorite } from "../utils/axiom.js";

export default function ExportFavorites({
  flags,
  highlights,
  onClose,
}) {
  const [includeHighlights, setIncludeHighlights] = useState(false);
  const [copied, setCopied] = useState(false);

  const payload = useMemo(() => {
    const favorites = { ...flags };
    if (includeHighlights) {
      for (const address of Object.keys(highlights || {})) {
        if (!favorites[address]) {
          favorites[address] = toFavorite(address, {
            name: shortName(address),
            emoji: "⭐",
            alertsOn: true,
          });
        }
      }
    }
    return toAxiomExport(favorites);
  }, [flags, highlights, includeHighlights]);

  const starredCount = Object.keys(flags).length;
  const highlightOnly = Object.keys(highlights || {}).filter((a) => !flags[a]).length;

  const doCopy = async () => {
    await copyJson(payload);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };

  const doDownload = () => {
    downloadJson(`axiom_wallets_${Date.now()}.json`, payload);
  };

  return createPortal(
    <div className="modal-backdrop" onClick={onClose}>
      <div className="export-modal" onClick={(e) => e.stopPropagation()}>
        <header className="star-modal-head">
          <h2>Export for Axiom</h2>
          <button type="button" className="modal-x" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>

        <p className="export-lead">
          Import this JSON into Axiom Trade’s tracked wallets. Names and emojis come from your
          starred favorites.
        </p>

        <div className="export-stats">
          <div className="export-stat">
            <strong>{starredCount}</strong>
            <span>starred</span>
          </div>
          <div className="export-stat">
            <strong>{payload.length}</strong>
            <span>in export</span>
          </div>
          {highlightOnly > 0 && (
            <div className="export-stat">
              <strong>{highlightOnly}</strong>
              <span>highlighted only</span>
            </div>
          )}
        </div>

        {highlightOnly > 0 && (
          <label className="star-toggle export-extra">
            <input
              type="checkbox"
              checked={includeHighlights}
              onChange={(e) => setIncludeHighlights(e.target.checked)}
            />
            Include highlighted wallets not yet starred
            <span className="export-hint">uses ⭐ + short address name</span>
          </label>
        )}

        {payload.length === 0 ? (
          <div className="export-empty">
            Star wallets with ★ first — you’ll set a name and emoji when you do.
          </div>
        ) : (
          <>
            <div className="export-list">
              {payload.map((item) => (
                <div key={item.trackedWalletAddress} className="export-row">
                  <span className="export-emoji">{item.emoji}</span>
                  <div className="export-row-main">
                    <strong>{item.name}</strong>
                    <code>{item.trackedWalletAddress}</code>
                  </div>
                  <span className={`export-alert${item.alertsOn ? " on" : ""}`}>
                    {item.alertsOn ? "alerts on" : "alerts off"}
                  </span>
                </div>
              ))}
            </div>

            <pre className="export-json">{JSON.stringify(payload, null, 2)}</pre>
          </>
        )}

        <footer className="star-modal-actions">
          <button type="button" className="btn" onClick={onClose}>
            Close
          </button>
          <div className="star-modal-actions-right">
            <button type="button" className="btn" onClick={doCopy} disabled={!payload.length}>
              {copied ? "Copied" : "Copy JSON"}
            </button>
            <button type="button" className="btn primary" onClick={doDownload} disabled={!payload.length}>
              Download .json
            </button>
          </div>
        </footer>
      </div>
    </div>,
    document.body
  );
}
