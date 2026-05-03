import { Link, useLocation } from "react-router-dom";
import { MapPinned, Plane } from "lucide-react";
import { API_BASE_URL } from "../api.js";

export function AppShell({ children }) {
  const location = useLocation();
  const isInput = location.pathname === "/";

  return (
    <div className="app-shell">
      <header className="topbar">
        <Link to="/" className="brand" aria-label="SquadPlanner AI home">
          <span className="brand-mark">
            <MapPinned size={20} />
          </span>
          <span>
            <strong>SquadPlanner AI</strong>
            <small>Trip planning workspace</small>
          </span>
        </Link>
        <div className="api-pill" title={API_BASE_URL}>
          <Plane size={16} />
          <span>{new URL(API_BASE_URL).host}</span>
        </div>
      </header>
      <main className={isInput ? "page page-input" : "page"}>{children}</main>
    </div>
  );
}
