import { useState } from "react";
import { api, type ProjectInfo } from "../api";

export default function Projects() {
  const [name, setName] = useState("");
  const [board, setBoard] = useState("nucleo_f411re");
  const [outputDir, setOutputDir] = useState("");
  const [result, setResult] = useState<ProjectInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await api.createProject({
        name,
        board,
        output_dir: outputDir || undefined,
      });
      setResult(data);
    } catch (e: any) {
      setError(e.message || "Failed to create project");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>Create Project</h2>
      <div className="form">
        <label>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label>
          Board
          <input value={board} onChange={(e) => setBoard(e.target.value)} />
        </label>
        <label>
          Output Dir
          <input value={outputDir} onChange={(e) => setOutputDir(e.target.value)} placeholder="optional" />
        </label>
        <button onClick={submit} disabled={!name || loading}>
          {loading ? "Creating..." : "Create"}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {result && (
        <div className="card">
          <p>Created: <code>{result.path}</code></p>
          <p>Board: {result.board}</p>
        </div>
      )}
    </div>
  );
}
