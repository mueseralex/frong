/** Shared top nav — same chrome on database, packs, and (via HTML twin) upload/API/home. */

const LINKS = [
  { key: "home", href: "/", label: "Home" },
  { key: "database", href: "/wallets/", label: "Database" },
  { key: "packs", href: "/wallets/packs/", label: "Packs" },
  { key: "api", href: "/wallets/api/", label: "API" },
  { key: "upload", href: "/upload/", label: "Upload" },
];

export default function FrongNav({ active = "database" }) {
  return (
    <header className="topbar">
      <a className="brand" href="/">
        frong.ai
      </a>
      <div className="tagline">Robinhood chain · wallets, packs, and frog desk</div>
      <nav className="topnav" aria-label="Site">
        {LINKS.map(({ key, href, label }) =>
          key === active ? (
            <span key={key} className="nav-link nav-link-active" aria-current="page">
              {label}
            </span>
          ) : (
            <a key={key} className="nav-link" href={href}>
              {label}
            </a>
          )
        )}
        <a
          className="nav-link"
          href="https://x.com/frong_ai"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Follow @frong_ai on X"
        >
          @frong_ai
        </a>
      </nav>
    </header>
  );
}
