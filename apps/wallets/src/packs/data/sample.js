/** Sample pack tiers + wallet pool for local UI prototyping only. */

/** Rarity ladder: pink (best) > purple > white (common). */
export const RARITIES = {
  white: {
    key: "white",
    label: "White",
    weight: 62,
    color: "#f7f2f5",
    glow: "rgba(255, 255, 255, 0.65)",
  },
  purple: {
    key: "purple",
    label: "Purple",
    weight: 28,
    color: "#a855f7",
    glow: "rgba(168, 85, 247, 0.5)",
  },
  pink: {
    key: "pink",
    label: "Pink",
    weight: 10,
    color: "#f23db8",
    glow: "rgba(242, 61, 184, 0.55)",
  },
};

/** Back-compat aliases used by older pull UI bits. */
RARITIES.common = RARITIES.white;
RARITIES.uncommon = RARITIES.white;
RARITIES.rare = RARITIES.purple;
RARITIES.epic = RARITIES.purple;
RARITIES.god = RARITIES.pink;

export const PACK_TIERS = [
  {
    id: "b",
    name: "White Pack",
    shortName: "White",
    priceLabel: "$2",
    price: 2,
    wallets: 3,
    blurb: "3 wallet collection · mostly whites, chase a purple.",
    description:
      "Entry pack for scanning the board. Three AI-scored Robinhood wallets — mostly White pulls, with a real shot at Purple.",
    highlights: ["3 wallets", "Chase a Purple", "Best for volume scanning"],
    accent: "#f4eef2",
    oddsBoost: 0,
    img: "/wallets/pack-art/white-v5.png",
  },
  {
    id: "a",
    name: "Purple Pack",
    shortName: "Purple",
    priceLabel: "$10",
    price: 10,
    wallets: 4,
    blurb: "4 wallet collection · better Purple / Pink odds.",
    description:
      "Mid pack with sharper odds. Four wallets weighted toward Purple and Pink pulls — stronger archetypes for your tracker.",
    highlights: ["4 wallets", "Boosted Purple / Pink", "Balanced chase pack"],
    accent: "#a855f7",
    oddsBoost: 0.16,
    img: "/wallets/pack-art/purple-v5.png",
  },
  {
    id: "s",
    name: "Pink Pack",
    shortName: "Pink",
    priceLabel: "$50",
    price: 50,
    wallets: 5,
    blurb: "5 wallet collection · guaranteed Purple+.",
    description:
      "Top pack. Five wallets with a guaranteed Purple or better on the first pull, plus the highest Pink weight. Built for high-conviction tracking lists.",
    highlights: ["5 wallets", "Purple+ guaranteed", "Highest Pink odds"],
    accent: "#f23db8",
    oddsBoost: 0.32,
    guaranteedMin: "purple",
    img: "/wallets/pack-art/pink-v5.png",
  },
];

const POOL = [
  {
    address: "0x3dd47ab4e8c2f1a90b6d4e2c91f0a1be8014",
    score: 83.4,
    archetype: "moonshot hunter",
    profit: 119000,
    winrate: 0.69,
    tokens: 229,
    brief: "Top-tier exit discipline. High conviction on sub-$250K FDV runners.",
  },
  {
    address: "0x3e30f44b91a7c8d2e5f60123456789abcc3f49",
    score: 80.7,
    archetype: "moonshot hunter",
    profit: 46100,
    winrate: 0.66,
    tokens: 142,
    brief: "Consistent early entries. Rotates cleanly before the dump.",
  },
  {
    address: "0xc2af01d8e4b7a6930123456789abcdef842740",
    score: 77.4,
    archetype: "consistent grinder",
    profit: 496700,
    winrate: 0.94,
    tokens: 850,
    brief: "Volume machine. Boring wins stacked over hundreds of trades.",
  },
  {
    address: "0x885419a1b2c3d4e5f678901234567890325cf6",
    score: 77.8,
    archetype: "sniper",
    profit: 88200,
    winrate: 0.71,
    tokens: 96,
    brief: "Tight entries on fresh launches. Cuts losers fast.",
  },
  {
    address: "0x1a2b3c4d5e6f7890abcdef1234567890aa11bb",
    score: 74.2,
    archetype: "rotation desk",
    profit: 31200,
    winrate: 0.61,
    tokens: 410,
    brief: "Rotates bags before narrative dies. Mid-cap specialist.",
  },
  {
    address: "0xabcdef0123456789fedcba9876543210cc22dd",
    score: 86.1,
    archetype: "degen oracle",
    profit: 210400,
    winrate: 0.73,
    tokens: 188,
    brief: "High score conviction. Early on runners that actually stick.",
  },
  {
    address: "0x99887766554433221100ffeeddccbbaa776655",
    score: 69.5,
    archetype: "scalper",
    profit: 18400,
    winrate: 0.58,
    tokens: 620,
    brief: "Quick flips. Survives chop with small edges stacked.",
  },
  {
    address: "0x11223344556677889900aabbccddeeff001122",
    score: 81.9,
    archetype: "moonshot hunter",
    profit: 70500,
    winrate: 0.65,
    tokens: 339,
    brief: "High token throughput with above-median score.",
  },
];

const ORDER = ["white", "purple", "pink"];

function weightedPick(boost = 0, minKey = null) {
  const minIdx = minKey ? ORDER.indexOf(minKey) : 0;
  const entries = ORDER.slice(Math.max(0, minIdx)).map((key) => {
    const base = RARITIES[key].weight;
    const bumped = key === "white" ? base * (1 - boost) : base * (1 + boost * (ORDER.indexOf(key) + 1));
    return { key, w: Math.max(0.2, bumped) };
  });
  const total = entries.reduce((s, e) => s + e.w, 0);
  let r = Math.random() * total;
  for (const e of entries) {
    r -= e.w;
    if (r <= 0) return e.key;
  }
  return entries[entries.length - 1].key;
}

function shortAddr(a) {
  return `${a.slice(0, 6)}…${a.slice(-4)}`;
}

function money(n) {
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(1)}K`;
  return `$${Math.round(n)}`;
}

/** Build a random pack pull from the sample pool. */
export function openSamplePack(tier) {
  const used = new Set();
  const cards = [];
  for (let i = 0; i < tier.wallets; i++) {
    let wallet;
    do {
      wallet = POOL[Math.floor(Math.random() * POOL.length)];
    } while (used.has(wallet.address) && used.size < POOL.length);
    used.add(wallet.address);

    const rarity =
      i === 0 && tier.guaranteedMin
        ? weightedPick(tier.oddsBoost, tier.guaranteedMin)
        : weightedPick(tier.oddsBoost);

    let finalRarity = rarity;
    if (wallet.score >= 82 && Math.random() < 0.35) finalRarity = "pink";
    else if (wallet.score >= 78 && ORDER.indexOf(finalRarity) < ORDER.indexOf("purple")) {
      if (Math.random() < 0.4) finalRarity = "purple";
    }

    const short = shortAddr(wallet.address);
    cards.push({
      id: `${wallet.address}-${i}-${Date.now()}`,
      ...wallet,
      rarity: finalRarity,
      short,
      profitLabel: money(wallet.profit),
      winLabel: `${Math.round(wallet.winrate * 100)}%`,
      name: `${wallet.archetype} · ${wallet.score}`,
    });
  }

  cards.sort((a, b) => ORDER.indexOf(a.rarity) - ORDER.indexOf(b.rarity));
  return {
    tierId: tier.id,
    tierName: tier.name,
    openedAt: new Date().toISOString(),
    cards,
  };
}

export function toAxiomExport(cards) {
  return cards.map((c) => ({
    trackedWalletAddress: c.address,
    name: `${c.archetype} · ${c.score}`,
    emoji: "",
    alertsOn: true,
  }));
}
