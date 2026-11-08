export async function api<T>(path: string, token: string | null, init: RequestInit = {}): Promise<T> {
  const response = await rawApi(path, token, init);
  return response.status === 204 ? undefined as T : response.json();
}
export async function rawApi(path: string, token: string | null, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (typeof init.body === "string") headers.set("Content-Type", "application/json");
  const response = await fetch(`/api/backend${path}`, { ...init, headers, cache: "no-store" });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.message || `Request failed (${response.status}). Please retry.`);
  }
  return response;
}
