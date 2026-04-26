import { useState } from "react";
import { api, type ProjectInfo } from "../api";

export default function Fix() {
  const [projectDir, setProjectDir] = useState("");
  const [prompt, setPrompt] = useState("");
  const [buildError, setBuildError] = useState("");
  const [board, setBoard] = useState("nucleo_f411re");
  const [result, setResult] = useState<ProjectInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await api.fix({
        project_dir: projectDir,
        prompt,
        build_error: buildError,
        board,
      });
      setResult(data);
    } catch (e: any) {
      setError(e.message || "Fix failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>Fix</h2>
      <div className="form">
        <label>
          Project Dir
          <input value={projectDir} onChange={(e) => setProjectDir(e.target.value)} />
        </label>
        <label>
          Original Prompt
          <input value={prompt} onChange={(e) => setPrompt(e.target.value)} />
        </label>
        <label>
          Board
          <input value={board} onChange={(e) => setBoard(e.target.value)} />
        </label>
        <label>
          Build Error
          <textarea value={buildError} onChange={(e) => setBuildError(e.target.value)} rows={6} />
        </label>
        <button onClick={submit} disabled={!projectDir || !prompt || !buildError || loading}>
          {loading ? "Fixing..." : "Fix"}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {result && (
        <div className="card">
          <p>Fixed: <code>{result.path}</code></p>
        </div>
      )}
    </div>
  );
}
