import { NavLink, useLocation } from "react-router-dom";
import { useEffect } from "react";
import Logo from "./Logo.jsx";

const LINKS = [
  { to: "/", label: "Home", end: true },
  { to: "/matcher", label: "Find Trials" },
  { to: "/trials", label: "Trial Database" },
  { to: "/evaluation", label: "Model Evaluation" },
];

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0); // block body: always returns undefined (a valid no-cleanup effect)
  }, [pathname]);
  return null;
}

export default function Layout({ children }) {
  return (
    <div>
      <ScrollToTop />
      <nav className="navbar">
        <div className="navbar-inner">
          <NavLink to="/" className="brand">
            <Logo />
            <span className="brand-text">
              <span className="brand-name">Clinical Trial <span className="brand-accent">Qualifier</span></span>
              <span className="brand-tag">AI-Powered Clinical Trial Matching</span>
            </span>
          </NavLink>
          <div className="nav-links">
            {LINKS.map((l) => (
              <NavLink key={l.to} to={l.to} end={l.end}
                className={({ isActive }) => (isActive ? "active" : "")}>
                {l.label}
              </NavLink>
            ))}
          </div>
        </div>
      </nav>
      <main className="container">{children}</main>
      <footer className="footer">
        <div>Clinical Trial Qualifier · Trial metadata: Clinical Trials Registry - India (CTRI)</div>
      </footer>
    </div>
  );
}
