export function originError(input: { url: string; host: string | null; origin: string | null; mode: string; environment?: string; webOrigin?: string }): string | null {
  if (input.environment === "production" && (input.mode !== "supabase" || !input.webOrigin)) {
    return "Hosted operation requires Supabase authentication and a configured web origin.";
  }
  try {
    // Next.js may normalize request.url to its internal hostname. Host is the
    // browser-facing authority; validate it explicitly instead of dropping CSRF checks.
    const host = new URL(`${new URL(input.url).protocol}//${input.host || ""}`);
    if (host.host !== input.host?.toLowerCase() || host.username || host.password) return "Invalid request host.";
    if (input.mode === "local" && !["127.0.0.1", "localhost", "[::1]"].includes(host.hostname)) {
      return "Local workspace mode is available on localhost only.";
    }
    const expected = input.webOrigin ? new URL(input.webOrigin).origin : host.origin;
    if (input.origin && input.origin !== expected) return "Cross-origin requests are not permitted.";
  } catch { return "Invalid request origin."; }
  return null;
}
