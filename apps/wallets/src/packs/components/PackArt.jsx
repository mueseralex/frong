/**
 * Sealed pack — metallic foil PNG (original style). No website logo overlay.
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

  if (!img) return null;

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
    </div>
  );
}
