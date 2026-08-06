// Production build sets VITE_API_URL=https://api.frong.ai (wallet DB stays on the VM).
// In local Vite, leave empty so /api/* proxies to the public API.
const BASE = import.meta.env.VITE_API_URL || "";

export async function fetchWallets(params) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "" && v !== false) qs.set(k, v);
  }
  const res = await fetch(`${BASE}/api/wallets?${qs}`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function fetchSummary() {
  const res = await fetch(`${BASE}/api/summary`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}
