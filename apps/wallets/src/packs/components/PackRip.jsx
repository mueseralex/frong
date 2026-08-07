import { useEffect, useRef, useState } from "react";
import PackArt from "./PackArt.jsx";
import WalletCert from "./WalletCert.jsx";
import { RARITIES } from "../data/sample.js";
import { burst, shake, sizeCanvas } from "../lib/fx.js";

/**
 * inspect → ready → charging → torn → reveal → summary
 * Inspect zooms the pack and shows description before the rip.
 */
export default function PackRip({ tier, pull, onDone, onClose }) {
  const [phase, setPhase] = useState("inspect");
  const [cardIdx, setCardIdx] = useState(0);
  const [hovered, setHovered] = useState(null);
  const canvasRef = useRef(null);
  const timers = useRef([]);

  const clearTimers = () => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  };

  const later = (fn, ms) => {
    const id = setTimeout(fn, ms);
    timers.current.push(id);
  };

  useEffect(() => {
    sizeCanvas(canvasRef.current);
    const onResize = () => sizeCanvas(canvasRef.current);
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      clearTimers();
    };
  }, []);

  const fireBurst = (rarityKey) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const colors = {
      white: ["#ffffff", "#f7f2f5", "#ffd0ef"],
      purple: ["#a855f7", "#ffffff", "#d8b4fe"],
      pink: ["#f23db8", "#ff4ec4", "#ffffff", "#ffe0f3"],
      common: ["#ffffff", "#f7f2f5", "#ffd0ef"],
      uncommon: ["#ffffff", "#f7f2f5", "#ffd0ef"],
      rare: ["#a855f7", "#ffffff", "#d8b4fe"],
      epic: ["#a855f7", "#ffffff", "#d8b4fe"],
      god: ["#f23db8", "#ff4ec4", "#ffffff", "#ffe0f3"],
    };
    const cols = colors[rarityKey] || colors.purple;
    const count = rarityKey === "pink" || rarityKey === "god" ? 140 : rarityKey === "purple" || rarityKey === "epic" ? 100 : 55;
    const power = rarityKey === "pink" || rarityKey === "god" ? 16 : 12;
    burst(canvas, innerWidth / 2, innerHeight / 2, cols, count, power);
    if (rarityKey === "pink" || rarityKey === "purple" || rarityKey === "god" || rarityKey === "epic") {
      later(() => burst(canvas, innerWidth * 0.35, innerHeight * 0.4, cols, 50, 11), 200);
      later(() => burst(canvas, innerWidth * 0.65, innerHeight * 0.4, cols, 50, 11), 360);
    }
  };

  const goSummary = () => {
    setPhase("summary");
    onDone?.();
  };

  const beginRip = () => {
    if (phase !== "inspect") return;
    setPhase("ready");
  };

  const startCharge = () => {
    if (phase !== "ready") return;
    setPhase("charging");
    later(() => {
      setPhase("torn");
      shake("sm");
      const canvas = canvasRef.current;
      if (canvas) {
        burst(canvas, innerWidth / 2, innerHeight / 2, ["#ffe0f3", "#f23db8", "#ffffff"], 46, 10);
      }
      later(() => {
        setCardIdx(0);
        setPhase("reveal");
        const first = pull.cards[0];
        fireBurst(first?.rarity || "purple");
        shake(first?.rarity === "pink" || first?.rarity === "purple" ? "lg" : "sm");
      }, 700);
    }, 980);
  };

  const nextCard = () => {
    if (cardIdx < pull.cards.length - 1) {
      const next = cardIdx + 1;
      setCardIdx(next);
      fireBurst(pull.cards[next].rarity);
      shake(pull.cards[next].rarity === "pink" || pull.cards[next].rarity === "purple" ? "lg" : "sm");
    } else {
      goSummary();
    }
  };

  useEffect(() => {
    if (phase !== "reveal") return;
    const id = setTimeout(() => {
      if (cardIdx < pull.cards.length - 1) nextCard();
      else goSummary();
    }, 2000);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, cardIdx]);

  if (!tier || !pull) return null;

  const card = pull.cards[cardIdx];
  const rarity = card ? RARITIES[card.rarity] : null;
  const showInspect = phase === "inspect";
  const showPack = phase === "ready" || phase === "charging" || phase === "torn";
  const showReveal = phase === "reveal";
  const showSummary = phase === "summary";
  const focusCard = hovered != null ? pull.cards[hovered] : null;

  return (
    <div className="rip-overlay">
      <canvas ref={canvasRef} id="confettiCanvas" />
      <div className="rip-vignette" />
      <div
        className={`rip-flash${phase === "torn" ? " go" : ""}`}
        key={phase === "torn" ? "flash" : "idle"}
      />
      <button type="button" className="rip-x" onClick={onClose} aria-label="Close">
        Close
      </button>

      {!showSummary && !showInspect && (
        <div
          className="rip-glow"
          style={{
            opacity: phase === "charging" || showReveal ? 1 : 0,
            ["--glow-color"]: rarity ? rarity.glow : "rgba(242, 61, 184, 0.35)",
          }}
        />
      )}
      {(card?.rarity === "purple" || card?.rarity === "pink") &&
        showReveal && (
          <div
            className="rip-rays"
            style={{ ["--ray-color"]: rarity?.glow || "rgba(242,61,184,0.14)" }}
          />
        )}

      <div className={`rip-stage${showSummary ? " summary-mode" : ""}${showInspect ? " inspect-mode" : ""}`}>
        {showInspect && (
          <div className="pack-inspect" style={{ "--tier": tier.accent }}>
            <div className="pack-inspect-art">
              <PackArt tier={tier} className="pack-inspect-pack" />
            </div>
            <div className="pack-inspect-panel">
              <p className="eyebrow">Sealed pack</p>
              <h2>{tier.name}</h2>
              <p className="pack-inspect-price">{tier.priceLabel}</p>
              <p className="pack-inspect-desc">{tier.description || tier.blurb}</p>
              <ul className="pack-inspect-list">
                {(tier.highlights || []).map((h) => (
                  <li key={h}>{h}</li>
                ))}
              </ul>
              <div className="pack-inspect-meta">
                <span>{tier.wallets} wallets</span>
                {tier.guaranteedMin && <span>Rare+ guaranteed</span>}
                <span>v1.1 collection</span>
              </div>
              <div className="pack-inspect-actions">
                <button type="button" className="btn primary big" onClick={beginRip}>
                  Rip this pack
                </button>
                <button type="button" className="btn" onClick={onClose}>
                  Back
                </button>
              </div>
            </div>
          </div>
        )}

        {showPack && (
          <>
            <div className={`rip-pack-zone ${phase}`}>
              {phase === "torn" ? (
                <>
                  <div className="rip-half half-top">
                    <PackArt tier={tier} />
                  </div>
                  <div className="rip-half half-bottom">
                    <PackArt tier={tier} />
                  </div>
                  <div className="seal-fly">
                    <div className="wax-seal" aria-hidden />
                  </div>
                </>
              ) : (
                <button
                  type="button"
                  className="pack-hit"
                  onClick={startCharge}
                  aria-label="Rip pack"
                >
                  <PackArt tier={tier} />
                </button>
              )}
            </div>
            {phase === "ready" && (
              <div className="rip-hint">Click the pack to rip it</div>
            )}
          </>
        )}

        {showReveal && card && (
          <div className="rip-card-zone" key={`${card.id}-${cardIdx}`}>
            <WalletCert
              card={card}
              serial={String(1000000 + cardIdx * 111 + ((card.score * 100) | 0)).padStart(7, "0")}
            />
            <p className="rip-sub">
              {cardIdx + 1} / {pull.cards.length} · AI-analyzed wallet
            </p>
            {cardIdx < pull.cards.length - 1 && (
              <button type="button" className="btn primary" onClick={nextCard}>
                Next pull
              </button>
            )}
          </div>
        )}

        {showSummary && (
          <div className="pull-summary">
            <header className="pull-summary-head">
              <p className="eyebrow">{tier.name} · pack complete</p>
              <h2>Your pulls</h2>
              <p>Select a card to enlarge · {pull.cards.length} wallets</p>
            </header>

            <div className={`pull-summary-grid count-${pull.cards.length}`}>
              {pull.cards.map((c, i) => (
                <button
                  key={c.id}
                  type="button"
                  className={`pull-thumb${hovered === i ? " is-hot" : ""}${
                    hovered != null && hovered !== i ? " is-dim" : ""
                  }`}
                  style={{ "--rc": (RARITIES[c.rarity] || RARITIES.common).color }}
                  onMouseEnter={() => setHovered(i)}
                  onMouseLeave={() => setHovered(null)}
                  onFocus={() => setHovered(i)}
                  onBlur={() => setHovered(null)}
                >
                  <span className="pull-thumb-rarity">
                    {(RARITIES[c.rarity] || RARITIES.common).label}
                  </span>
                  <strong className="pull-thumb-score">{c.score.toFixed(1)}</strong>
                  <span className="pull-thumb-arch">{c.archetype}</span>
                  <code className="pull-thumb-addr">{c.short}</code>
                  <span className="pull-thumb-meta">
                    {c.profitLabel} · {c.winLabel}
                  </span>
                </button>
              ))}
            </div>

            {focusCard && (
              <div className="pull-focus" key={focusCard.id}>
                <WalletCert
                  card={focusCard}
                  serial={String(
                    1000000 + hovered * 111 + ((focusCard.score * 100) | 0)
                  ).padStart(7, "0")}
                />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
