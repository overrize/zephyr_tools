import { useState } from "react";
import { api, type BuildResult } from "../api";

export default function Build() {
  const [projectDir, setProjectDir] = useState("");
  const [board, setBoard] = useState("nucleo_f411re");
  const [buildDir, setBuildDir] = useState("");
  const [pristine, setPristine] = useState(false);
  const [result, setResult] = useState<BuildResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await api.build({
        project_dir: projectDir,
        board,
        build_dir: buildDir || undefined,
        pristine,
      });
      setResult(data);
    } catch (e: any) {
      setError(e.message || "Build failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>Build</h2>
      <div className="form">
        <label>
          Project Dir
          <input value={projectDir} onChange={(e) => setProjectDir(e.target.value)} />
        </label>
        <label>
          Board
          <input value={board} onChange={(e) => setBoard(e.target.value)} />
        </label>
        <label>
          Build Dir
          <input value={buildDir} onChange={(e) => setBuildDir(e.target.value)} placeholder="optional" />
        </label>
        <label className="row">
          <input type="checkbox" checked={pristine} onChange={(e) => setPristine(e.target.checked)} />
          Pristine build
        </label>
        <button onClick={submit} disabled={!projectDir || loading}>
          {loading ? "Building..." : "Build"}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {result && (
        <div className="card">
          <p>Status: {result.ok ? "OK" : "FAILED"}</p>
          <p>Build Dir: <code>{result.build_dir}</code></p>
          {result.elf_path && <p>ELF: <code>{result.elf_path}</code></p>}
        </div>
      )}
    </div>
  );
}
