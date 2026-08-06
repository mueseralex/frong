/** Shared top nav for database + packs pages (frong.ai). */

export default function FrongNav({ active = "database" }) {
  const item = (key, href, label) => {
    if (key === active) {
      return (
        <span className="nav-link nav-link-active" aria-current="page">
          {label}
        </span>
      );
    }
    return (
      <a className="nav-link" href={href}>
        {label}
      </a>
    );
  };

  return (
    <header className="topbar">
      <a className="brand brand-with-logo" href="/">
        <img src="/wallets/frong.svg" alt="" />
        frong.ai
      </a>
      <div className="tagline">Robinhood chain · wallets, packs, and frog desk</div>
      {item("chat", "/", "Chat")}
      {item("database", "/wallets/", "Database")}
      {item("packs", "/wallets/packs/", "Packs")}
      {item("api", "/wallets/api/", "API")}
      <a className="nav-link" href="/upload/">
        Upload
      </a>
      <a
        className="nav-link"
        href="https://x.com/frong_ai"
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Follow @frong_ai on X"
      >
        @frong_ai
      </a>
    </header>
  );
}
