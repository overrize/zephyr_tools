const API_BASE = "http://127.0.0.1:8765";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "content-type": "application/json" },
    ...init,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `HTTP ${res.status}`);
  }
  return data as T;
}

export type DoctorCheck = {
  name: string;
  ok: boolean;
  detail: string;
  hint?: string;
};

export type BoardInfo = {
  name: string;
  vendor?: string;
  arch?: string;
  soc?: string;
};

export type ProjectInfo = {
  name: string;
  path: string;
  board: string;
};

export type BuildResult = {
  project_dir: string;
  build_dir: string;
  board: string;
  elf_path?: string;
  ok: boolean;
};

export type CommandResult = {
  ok: boolean;
  output?: string;
  returncode?: number;
};

export const api = {
  doctor: () => request<DoctorCheck[]>("/doctor"),
  boards: (filter?: string) =>
    request<BoardInfo[]>(`/boards${filter ? `?filter=${encodeURIComponent(filter)}` : ""}`),
  createProject: (body: { name: string; board?: string; output_dir?: string; overwrite?: boolean }) =>
    request<ProjectInfo>("/projects", { method: "POST", body: JSON.stringify(body) }),
  build: (body: { project_dir: string; board?: string; build_dir?: string; pristine?: boolean }) =>
    request<BuildResult>("/build", { method: "POST", body: JSON.stringify(body) }),
  flash: (body: { build_dir: string; runner?: string }) =>
    request<CommandResult>("/flash", { method: "POST", body: JSON.stringify(body) }),
  generate: (body: { prompt: string; output_dir?: string; board?: string }) =>
    request<ProjectInfo>("/generate", { method: "POST", body: JSON.stringify(body) }),
  fix: (body: { project_dir: string; prompt: string; build_error: string; board?: string }) =>
    request<ProjectInfo>("/fix", { method: "POST", body: JSON.stringify(body) }),
};
