import { Link, Outlet, useLocation } from "react-router-dom";

const TABS = [
  ["/", "Home"],
  ["/chat", "Chat"],
  ["/sessions", "Sessions"],
  ["/assets", "Assets"],
  ["/admin", "Admin"],
] as const;

export function App() {
  const { pathname } = useLocation();
  return (
    <div className="shell">
      <header className="topbar">
        <span className="brand">🛡️ agentic-webapp</span>
        <nav>
          {TABS.map(([to, label]) => (
            <Link key={to} to={to} className={pathname === to ? "tab active" : "tab"}>
              {label}
            </Link>
          ))}
        </nav>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
