import { useState } from "react";
import { api, type CommandResult } from "../api";

export default function Flash() {
  const [buildDir, setBuildDir] = useState("build");
  const [runner, setRunner] = useState("");
  const [result, setResult] = useState<CommandResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await api.flash({
        build_dir: buildDir,
        runner: runner || undefined,
      });
      setResult(data);
    } catch (e: any) {
      setError(e.message || "Flash failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>Flash</h2>
      <div className="form">
        <label>
          Build Dir
          <input value={buildDir} onChange={(e) => setBuildDir(e.target.value)} />
        </label>
        <label>
          Runner
          <input value={runner} onChange={(e) => setRunner(e.target.value)} placeholder="optional" />
        </label>
        <button onClick={submit} disabled={!buildDir || loading}>
          {loading ? "Flashing..." : "Flash"}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {result && (
        <div className="card">
          <p>Status: {result.ok ? "OK" : "FAILED"}</p>
          {result.output && <pre>{result.output}</pre>}
        </div>
      )}
    </div>
  );
}
