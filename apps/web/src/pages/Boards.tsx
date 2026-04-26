import { useState } from "react";
import { api, type BoardInfo } from "../api";

export default function Boards() {
  const [filter, setFilter] = useState("");
  const [boards, setBoards] = useState<BoardInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const search = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.boards(filter || undefined);
      setBoards(data);
    } catch (e: any) {
      setError(e.message || "Failed to load boards");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>Boards</h2>
      <div className="row">
        <input
          placeholder="Filter by name"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <button onClick={search}>Search</button>
      </div>
      {loading && <p>Loading...</p>}
      {error && <p className="error">{error}</p>}
      <ul className="list">
        {boards.map((b) => (
          <li key={b.name} className="card">
            {b.name}
          </li>
        ))}
      </ul>
    </div>
  );
}
