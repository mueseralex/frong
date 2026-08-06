import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { EMOJI_PRESETS, shortName } from "../utils/axiom.js";

export default function StarModal({ address, initial, onSave, onUnstar, onClose }) {
  const [name, setName] = useState(initial?.name || shortName(address));
  const [emoji, setEmoji] = useState(initial?.emoji || "⭐");
  const [alertsOn, setAlertsOn] = useState(initial?.alertsOn !== false);
  const editing = !!initial;

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const submit = (e) => {
    e.preventDefault();
    onSave({ name, emoji, alertsOn });
  };

  return createPortal(
    <div className="modal-backdrop" onClick={onClose}>
      <form className="star-modal" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <header className="star-modal-head">
          <h2>{editing ? "Edit Favorite" : "Star Wallet"}</h2>
          <button type="button" className="modal-x" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>

        <p className="star-modal-addr" title={address}>
          {address}
        </p>

        <label className="star-field">
          <span>Name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={48}
            placeholder="e.g. Alpha sniper"
            autoFocus
          />
        </label>

        <div className="star-field">
          <span>Emoji</span>
          <div className="emoji-row">
            {EMOJI_PRESETS.map((item) => (
              <button
                key={item}
                type="button"
                className={`emoji-chip${emoji === item ? " active" : ""}`}
                onClick={() => setEmoji(item)}
              >
                {item}
              </button>
            ))}
            <input
              className="emoji-custom"
              value={emoji}
              onChange={(e) => setEmoji(e.target.value.slice(0, 4))}
              aria-label="Custom emoji"
              title="Custom emoji"
            />
          </div>
        </div>

        <label className="star-toggle">
          <input
            type="checkbox"
            checked={alertsOn}
            onChange={(e) => setAlertsOn(e.target.checked)}
          />
          Alerts on in Axiom
        </label>

        <div className="star-preview">
          <span className="star-preview-chip">
            {emoji || "⭐"} {name.trim() || shortName(address)}
          </span>
          <span className="star-preview-meta">
            {alertsOn ? "alerts on" : "alerts off"} · ready for Axiom export
          </span>
        </div>

        <footer className="star-modal-actions">
          {editing && (
            <button type="button" className="btn danger" onClick={onUnstar}>
              Unstar
            </button>
          )}
          <div className="star-modal-actions-right">
            <button type="button" className="btn" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn primary">
              {editing ? "Save" : "Star"}
            </button>
          </div>
        </footer>
      </form>
    </div>,
    document.body
  );
}
