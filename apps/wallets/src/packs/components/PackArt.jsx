/**
 * Sealed pack — foil PNG with emblem only (copy lives in UI / inspect panel).
 */
export default function PackArt({ tier, className = "" }) {
  const img = tier.img;
  const mask = img
    ? {
        WebkitMaskImage: `url('${img}')`,
        maskImage: `url('${img}')`,
        WebkitMaskSize: "contain",
        maskSize: "contain",
        WebkitMaskRepeat: "no-repeat",
        maskRepeat: "no-repeat",
        WebkitMaskPosition: "center",
        maskPosition: "center",
      }
    : undefined;

  if (img) {
    return (
      <div
        className={`pack pack-has-img pack-skin-${tier.id} ${className}`}
        style={{ "--pack-accent": tier.accent }}
        aria-label={`${tier.shortName || tier.name} sealed pack`}
      >
        <img
          className="pack-render"
          src={img}
          alt={`${tier.shortName || tier.name} pack`}
          draggable={false}
        />
        <div className="pack-sheen" style={mask} aria-hidden />
        <div className="wax-seal" aria-hidden>
          <img src="/wallets/frong.svg" alt="" />
        </div>
      </div>
    );
  }

  return (
    <div
      className={`pack pack-skin-${tier.id} ${className}`}
      style={{ "--pack-accent": tier.accent }}
    >
      <div className="pack-shell">
        <div className="pack-crimp pack-crimp-top" aria-hidden />
        <div className="pack-crimp pack-crimp-bot" aria-hidden />
        <div className="pack-foil">
          <div className="pack-badge">
            <img src="/wallets/frong.svg" alt="" />
          </div>
        </div>
      </div>
    </div>
  );
}
