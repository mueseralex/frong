import { RARITIES } from "../data/sample.js";

/** Session pull card — clean frong.ai style, no emojis. */
export default function WalletCard({ card }) {
  const rarity = RARITIES[card.rarity] || RARITIES.common;

  return (
    <article
      className={`opened-card rarity-${card.rarity}`}
      style={{ "--rc": rarity.color }}
      title={card.address}
    >
      <header className="opened-card-head">
        <span className="opened-rarity">{rarity.label}</span>
        <span className="opened-score">{card.score.toFixed(1)}</span>
      </header>

      <h3 className="opened-arch">{card.archetype}</h3>
      <code className="opened-addr">{card.short}</code>
      <p className="opened-brief">{card.brief}</p>

      <dl className="opened-stats">
        <div>
          <dt>Profit</dt>
          <dd>{card.profitLabel}</dd>
        </div>
        <div>
          <dt>Win</dt>
          <dd>{card.winLabel}</dd>
        </div>
        <div>
          <dt>Tokens</dt>
          <dd>{card.tokens}</dd>
        </div>
      </dl>
    </article>
  );
}
