const DEFAULT_EMOJI = "⭐";

export const EMOJI_PRESETS = ["⭐", "🐋", "🚀", "💎", "🔥", "🧠", "🥷", "📈", "🐂", "👀"];

export function shortName(address) {
  if (!address) return "Wallet";
  return address.length > 10 ? `${address.slice(0, 6)}…${address.slice(-4)}` : address;
}

/** Normalize legacy `{ addr: true }` flags into favorite objects. */
export function migrateFlags(raw) {
  if (!raw || typeof raw !== "object") return {};
  const out = {};
  for (const [address, value] of Object.entries(raw)) {
    if (!value) continue;
    if (typeof value === "object" && value.name) {
      out[address] = {
        name: String(value.name).slice(0, 48),
        emoji: value.emoji || DEFAULT_EMOJI,
        alertsOn: value.alertsOn !== false,
        starredAt: value.starredAt || null,
      };
    } else {
      out[address] = {
        name: shortName(address),
        emoji: DEFAULT_EMOJI,
        alertsOn: true,
        starredAt: null,
      };
    }
  }
  return out;
}

export function toFavorite(address, { name, emoji, alertsOn = true } = {}) {
  const trimmed = (name || "").trim();
  return {
    name: (trimmed || shortName(address)).slice(0, 48),
    emoji: (emoji || "").trim() || DEFAULT_EMOJI,
    alertsOn: !!alertsOn,
    starredAt: new Date().toISOString(),
  };
}

/** Axiom Trade tracked-wallet import shape. */
export function toAxiomExport(favorites, addresses = null) {
  const keys = addresses || Object.keys(favorites);
  return keys
    .filter((address) => favorites[address])
    .map((address) => {
      const fav = favorites[address];
      return {
        trackedWalletAddress: address,
        name: fav.name || shortName(address),
        emoji: fav.emoji || DEFAULT_EMOJI,
        alertsOn: fav.alertsOn !== false,
      };
    });
}

export function downloadJson(filename, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function copyJson(data) {
  const text = JSON.stringify(data, null, 2);
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const ta = document.createElement("textarea");
  ta.value = text;
  document.body.appendChild(ta);
  ta.select();
  document.execCommand("copy");
  ta.remove();
}
