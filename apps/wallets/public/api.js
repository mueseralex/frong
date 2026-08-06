const AI_GUIDE = `FRONG.AI PUBLIC API V1

Purpose:
Query a public database of Robinhood-chain wallet statistics or submit wallets for fresh asynchronous processing.

Authentication:
No API key is required.

Base URLs:
- Stored database: https://api.frong.ai
- Fresh batch processing: https://process.frong.ai

Rate and size limits:
- Database API: 120 requests per minute per IP.
- Wallet list: maximum 250 records per request; use page/per_page for pagination.
- Processing: 1 to 100 unique addresses per job.
- One active processing job per IP, with a short cooldown between jobs.
- Batch results expire after 48 hours.

DATABASE ENDPOINTS

1. GET https://api.frong.ai/v1/wallets
Returns:
{
  "page": 1,
  "per_page": 50,
  "total": 26786,
  "pages": 536,
  "wallets": [...]
}

Query parameters:
- page: integer >= 1, default 1
- per_page: integer 1-250, default 50
- sort_by: any field from /v1/fields, default total_profit
- order: asc or desc, default desc
- search: partial wallet address, maximum 100 characters
- fields: comma-separated response fields
- fdv_only: true or false
- min_profit / max_profit: total-profit range
- min_winrate / max_winrate: 30-day win-rate percentages from 0 to 100
- min_tokens / max_tokens: analyzed token-position range
- updated_since: ISO-8601 datetime
- filters: URL-encoded JSON object for advanced numeric ranges.
  Example: {"sub_75k_entries":{"min":5},"balance":{"max":10}}

Example:
GET https://api.frong.ai/v1/wallets?per_page=25&sort_by=total_profit&order=desc&min_winrate=60&fdv_only=true&fields=address,total_profit,winrate_30d

2. GET https://api.frong.ai/v1/wallets/{address}
Returns the latest stored snapshot for one exact 0x wallet.
Optional query parameter: fields=address,total_profit,winrate_30d
Returns 404 when the wallet is not in the stored database.

3. GET https://api.frong.ai/v1/summary
Returns chain, total_wallets, fdv_enriched, profitable_wallets, and last_update.

4. GET https://api.frong.ai/v1/fields
Returns every public field with type, description, sortable, and range_filterable metadata.

Public wallet fields:
address, total_profit, realized_profit_30d, unrealized_profit, all_pnl,
winrate_30d, buy_30d, sell_30d, balance, token_num, pnl_2x_5x_num,
pnl_gt_5x_num, kol_rank, avg_holding_period, no_buy_hold_ratio,
sub_75k_entries, sub_75k_avg_entry, sub_75k_avg_buy_amount,
sub_75k_avg_buy_30d, sub_75k_avg_sell_30d,
sub_75k_avg_total_profit_pnl, fdv_75k_250k_entries,
fdv_75k_250k_avg_entry, fdv_75k_250k_avg_buy_amount,
fdv_75k_250k_avg_buy_30d, fdv_75k_250k_avg_sell_30d,
fdv_75k_250k_avg_total_profit_pnl, fast_trades_percentage,
date_reviewed, updated_at.

Notes:
- winrate_30d is returned as a 0-1 fraction even though min_winrate/max_winrate accept 0-100 percentages.
- Use fields projection whenever possible to reduce response size.
- Follow pages until page >= pages to retrieve an entire filtered result set.

FRESH WALLET PROCESSING

Processing is asynchronous. Never wait for the POST request to return wallet data.

Step 1 — submit:
POST https://process.frong.ai/api/v1/batches
Content-Type: application/json
Body:
{
  "addresses": ["0x59050e6c37ed6bdd003966af9b061757c7f04757"],
  "note": "optional public note, maximum 80 characters, no links"
}
Response:
{"job_id":"UUID","total":1}

Step 2 — poll every 2-5 seconds:
GET https://process.frong.ai/api/v1/batches/{job_id}
The status is queued, processing, done, or error.
Progress fields include total, done, queue_position, and error.
When done, the response includes results_url and download_url.

Step 3 — retrieve results:
JSON: GET https://process.frong.ai/api/v1/batches/{job_id}/results
CSV:  GET https://process.frong.ai/api/v1/batches/{job_id}/results.csv

The job ID acts as a private access token. Do not publish or log it.
Successful fresh results are also inserted or updated in the main public database.

Error handling:
- 400: invalid parameters, addresses, fields, filters, or note
- 404: wallet/job not found
- 409: batch results requested before completion
- 429: rate limit, cooldown, or an existing active job
- 503: processing queue full
- Respect Retry-After when supplied.

Python database example:
import requests

response = requests.get(
    "https://api.frong.ai/v1/wallets",
    params={
        "per_page": 100,
        "min_profit": 10000,
        "min_winrate": 60,
        "sort_by": "total_profit",
        "order": "desc",
        "fields": "address,total_profit,winrate_30d,sub_75k_entries"
    },
    timeout=30
)
response.raise_for_status()
wallets = response.json()["wallets"]

JavaScript database example:
const url = new URL("https://api.frong.ai/v1/wallets");
url.search = new URLSearchParams({
  per_page: "100",
  min_profit: "10000",
  fields: "address,total_profit,winrate_30d"
});
const data = await fetch(url).then(r => {
  if (!r.ok) throw new Error(\`API \${r.status}\`);
  return r.json();
});
`;

const toast = document.getElementById("toast");
let toastTimer;

async function copyText(text, button) {
  try {
    await navigator.clipboard.writeText(text);
  } catch (_) {
    const area = document.createElement("textarea");
    area.value = text;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.append(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }
  if (button) {
    const original = button.textContent;
    button.textContent = "Copied";
    setTimeout(() => { button.textContent = original; }, 1400);
  }
  clearTimeout(toastTimer);
  toast.classList.add("show");
  toastTimer = setTimeout(() => toast.classList.remove("show"), 1800);
}

document.querySelectorAll(".copy-code").forEach((button) => {
  button.addEventListener("click", () => {
    const container = button.closest(".code-block");
    const code = container?.querySelector("code");
    if (code) copyText(code.textContent.trim(), button);
  });
});

document.querySelectorAll(".inline-copy").forEach((button) => {
  button.addEventListener("click", () => {
    const container = button.parentElement;
    const code = container?.querySelector("code");
    if (code) copyText(code.textContent.trim(), button);
  });
});

document.getElementById("copy-ai-guide")?.addEventListener("click", (event) => {
  copyText(AI_GUIDE, event.currentTarget);
});

const search = document.getElementById("doc-search");
search?.addEventListener("input", () => {
  const query = search.value.trim().toLowerCase();
  document.querySelectorAll(".api-item").forEach((item) => {
    const matches = !query || item.textContent.toLowerCase().includes(query);
    item.classList.toggle("search-hidden", !matches);
    if (query && matches) item.open = true;
  });
});

const navLinks = [...document.querySelectorAll(".sidebar nav a")];
navLinks.forEach((link) => {
  link.addEventListener("click", () => {
    navLinks.forEach((item) => item.classList.remove("active"));
    link.classList.add("active");
    const target = document.querySelector(link.getAttribute("href"));
    if (target?.tagName === "DETAILS") target.open = true;
  });
});

const observed = navLinks
  .map((link) => document.querySelector(link.getAttribute("href")))
  .filter(Boolean);

const observer = new IntersectionObserver((entries) => {
  const visible = entries
    .filter((entry) => entry.isIntersecting)
    .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
  if (!visible) return;
  navLinks.forEach((link) => {
    link.classList.toggle("active", link.getAttribute("href") === `#${visible.target.id}`);
  });
}, { rootMargin: "-70px 0px -70% 0px", threshold: 0 });

observed.forEach((target) => observer.observe(target));
