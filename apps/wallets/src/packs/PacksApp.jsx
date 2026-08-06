import { useMemo, useState } from "react";
import PackArt from "./components/PackArt.jsx";
import { PACK_TIERS, RARITIES } from "./data/sample.js";
import FrongNav from "../nav.jsx";

/** Set true when crypto checkout is live. */
const RIP_ENABLED = false;

export default function PacksApp() {
  const [selectedId, setSelectedId] = useState("a");

  const tier = useMemo(
    () => PACK_TIERS.find((t) => t.id === selectedId) || PACK_TIERS[0],
    [selectedId]
  );

  return (
    <div className="app">
      <FrongNav active="packs" />

      <div className="coming-banner" role="status">
        Browsing is open. Pack ripping is Coming Soon — crypto payments are not enabled yet.
      </div>

      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Frong Packs</p>
          <h1>
            Rip packs.
            <br />
            Pull wallets worth tracking.
          </h1>
          <p className="hero-sub">
            Sealed batches of AI-scored Robinhood-chain wallets. Rarity ladder: pink &gt; purple &gt;
            white. Export when ripping goes live.
          </p>
          <div className="hero-cta">
            <button
              type="button"
              className="btn primary big btn-coming-soon"
              disabled
              title="Crypto payments not enabled yet"
            >
              Coming Soon
            </button>
            <span className="hero-meta">
              {tier.wallets} wallets · {tier.priceLabel}
            </span>
          </div>
        </div>
        <div className="hero-pack">
          <div className="hero-pack-btn is-locked" aria-label={`${tier.shortName || tier.name} pack preview`}>
            <PackArt tier={tier} className="pack-hero" />
            <span className="pedestal-hint">Ripping Coming Soon</span>
          </div>
        </div>
      </section>

      <section className="tiers">
        <div className="section-head">
          <h2>Choose a pack</h2>
          <p>Preview tiers now. Purchase and rip unlock when payments go live.</p>
        </div>
        <div className="tier-grid">
          {PACK_TIERS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`tier-card ${selectedId === t.id ? "selected" : ""}`}
              style={{ "--tier": t.accent }}
              onClick={() => setSelectedId(t.id)}
            >
              <div className="tier-pack-preview">
                <PackArt tier={t} />
              </div>
              <div className="tier-top">
                <span className="tier-name">{t.shortName || t.name}</span>
                <span className="tier-price">{t.priceLabel}</span>
              </div>
              <p>{t.description || t.blurb}</p>
              <div className="tier-foot">
                <span>{t.wallets} pulls</span>
                {t.guaranteedMin && <span className="guarantee">Purple+ guaranteed</span>}
              </div>
              <div className="tier-rip-row">
                <span className="btn primary btn-coming-soon tier-rip-btn" aria-disabled="true">
                  Coming Soon
                </span>
              </div>
            </button>
          ))}
        </div>
      </section>

      <section className="odds">
        <div className="section-head">
          <h2>Rarity ladder</h2>
          <p>Pink is best. Then purple. White is common.</p>
        </div>
        <div className="odds-row">
          {Object.values(RARITIES).map((r) => (
            <div key={r.key} className="odds-chip" style={{ "--rarity": r.color }}>
              <span className="dot" />
              <strong>{r.label}</strong>
              <em>{r.weight}%</em>
            </div>
          ))}
        </div>
      </section>

      <footer className="foot">
        frong.ai packs · sample preview · not financial advice
        {RIP_ENABLED ? "" : " · ripping locked until payments launch"}
      </footer>
    </div>
  );
}
