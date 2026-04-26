import { useState } from "react";
import { api, type ProjectInfo } from "../api";

export default function Generate() {
  const [prompt, setPrompt] = useState("");
  const [outputDir, setOutputDir] = useState("generated");
  const [board, setBoard] = useState("nucleo_f411re");
  const [result, setResult] = useState<ProjectInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await api.generate({
        prompt,
        output_dir: outputDir,
        board,
      });
      setResult(data);
    } catch (e: any) {
      setError(e.message || "Generation failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>Generate</h2>
      <div className="form">
        <label>
          Prompt
          <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={4} />
        </label>
        <label>
          Output Dir
          <input value={outputDir} onChange={(e) => setOutputDir(e.target.value)} />
        </label>
        <label>
          Board
          <input value={board} onChange={(e) => setBoard(e.target.value)} />
        </label>
        <button onClick={submit} disabled={!prompt || loading}>
          {loading ? "Generating..." : "Generate"}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {result && (
        <div className="card">
          <p>Generated: <code>{result.path}</code></p>
          <p>Board: {result.board}</p>
        </div>
      )}
    </div>
  );
}
