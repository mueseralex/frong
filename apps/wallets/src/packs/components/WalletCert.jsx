import { RARITIES } from "../data/sample.js";

/** Reveal / focus card — same language as session pulls. */
export default function WalletCert({ card, serial }) {
  const rarity = RARITIES[card.rarity] || RARITIES.common;

  return (
    <article
      className={`pull-card rarity-${card.rarity}`}
      style={{ "--rc": rarity.color }}
    >
      <header className="pull-card-head">
        <span className="pull-rarity">{rarity.label}</span>
        <span className="pull-score">{card.score.toFixed(1)}</span>
      </header>

      <h3 className="pull-archetype">{card.archetype}</h3>
      <code className="pull-addr" title={card.address}>
        {card.short}
      </code>
      <p className="pull-brief">{card.brief}</p>

      <div className="pull-stats">
        <div>
          <span>Profit</span>
          <strong>{card.profitLabel}</strong>
        </div>
        <div>
          <span>Win</span>
          <strong>{card.winLabel}</strong>
        </div>
        <div>
          <span>Tokens</span>
          <strong>{card.tokens}</strong>
        </div>
      </div>

      <footer className="pull-card-foot">
        <span>frong.ai</span>
        <span>#{serial}</span>
      </footer>
    </article>
  );
}
