/**
 * Sealed pack — CSS foil skins (white / purple / pink). Frog seal only.
 */
export default function PackArt({ tier, className = "" }) {
  return (
    <div
      className={`pack pack-css pack-skin-${tier.id} ${className}`}
      style={{ "--pack-accent": tier.accent }}
      aria-label={`${tier.shortName || tier.name} sealed pack`}
    >
      <div className="pack-shell">
        <div className="pack-crimp pack-crimp-top" aria-hidden />
        <div className="pack-crimp pack-crimp-bot" aria-hidden />
        <div className="pack-foil">
          <div className="pack-foil-grain" aria-hidden />
          <div className="pack-foil-sheen" aria-hidden />
          <div className="pack-edge-hilite" aria-hidden />
          <div className="pack-badge">
            <img src="/wallets/frong.svg" alt="" />
          </div>
          <div className="pack-tier-label">{tier.shortName || tier.name}</div>
        </div>
      </div>
      <div className="pack-shadow" aria-hidden />
    </div>
  );
}
