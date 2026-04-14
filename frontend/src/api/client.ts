export class ApiError extends Error {
  status: number;
  body: string;
  constructor(status: number, body: string) {
    super(`API error ${status}: ${body}`);
    this.status = status;
    this.body = body;
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}

export async function apiDelete(path: string): Promise<void> {
  const res = await fetch(path, { method: 'DELETE' });
  if (!res.ok) throw new ApiError(res.status, await res.text());
}
