// Same-origin proxy on frong.ai — browsers never need api.* subdomain DNS.
const BASE = import.meta.env.VITE_API_URL || "/wallet-api";

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
