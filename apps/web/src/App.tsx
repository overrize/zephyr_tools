import { useState } from "react";
import "./App.css";
import Dashboard from "./pages/Dashboard";
import Boards from "./pages/Boards";
import Projects from "./pages/Projects";
import Build from "./pages/Build";
import Flash from "./pages/Flash";
import Generate from "./pages/Generate";
import Fix from "./pages/Fix";

type Page = "dashboard" | "boards" | "projects" | "build" | "flash" | "generate" | "fix";

const pages: { key: Page; label: string }[] = [
  { key: "dashboard", label: "Dashboard" },
  { key: "boards", label: "Boards" },
  { key: "projects", label: "Projects" },
  { key: "build", label: "Build" },
  { key: "flash", label: "Flash" },
  { key: "generate", label: "Generate" },
  { key: "fix", label: "Fix" },
];

export default function App() {
  const [page, setPage] = useState<Page>("dashboard");

  return (
    <div className="app">
      <aside className="sidebar">
        <h1>Zephyr Tools</h1>
        <nav>
          {pages.map((p) => (
            <button
              key={p.key}
              className={page === p.key ? "active" : ""}
              onClick={() => setPage(p.key)}
            >
              {p.label}
            </button>
          ))}
        </nav>
      </aside>
      <main className="content">
        {page === "dashboard" && <Dashboard />}
        {page === "boards" && <Boards />}
        {page === "projects" && <Projects />}
        {page === "build" && <Build />}
        {page === "flash" && <Flash />}
        {page === "generate" && <Generate />}
        {page === "fix" && <Fix />}
      </main>
    </div>
  );
}
