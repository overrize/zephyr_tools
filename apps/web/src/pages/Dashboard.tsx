import { useState, useEffect } from "react";
import { api, type DoctorCheck } from "../api";

export default function Dashboard() {
  const [checks, setChecks] = useState<DoctorCheck[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.doctor();
      setChecks(data);
    } catch (e: any) {
      setError(e.message || "Failed to load doctor results");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div>
      <h2>Environment Check</h2>
      {loading && <p>Loading...</p>}
      {error && <p className="error">{error}</p>}
      <ul className="list">
        {checks.map((c) => (
          <li key={c.name} className="card">
            <span className={c.ok ? "ok" : "fail"}>{c.ok ? "[OK]" : "[FAIL]"}</span>{" "}
            <strong>{c.name}</strong>: {c.detail}
            {c.hint && <div className="hint">Hint: {c.hint}</div>}
          </li>
        ))}
      </ul>
    </div>
  );
}
