import { NextRequest } from "next/server";
import { originError } from "@/lib/proxy-policy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const ALLOWED = /^(health|v1\/(capabilities|extract|sessions(?:\/[a-f0-9-]{36}(?:\/(answers|speech|transcribe|report|report\.pdf))?)?))$/;

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const route = path.join("/");
  if (!ALLOWED.test(route)) return Response.json({ message: "Route not found." }, { status: 404 });
  const mode = process.env.ROLEREADY_AUTH_MODE || "local";
  const policyError = originError({ url: request.url, host: request.headers.get("host"),
    origin: request.headers.get("origin"), mode, environment: process.env.ROLEREADY_ENVIRONMENT,
    webOrigin: process.env.ROLEREADY_WEB_ORIGIN });
  if (policyError) return Response.json({ message: policyError }, { status: 403 });
  let body: Uint8Array | undefined;
  if (!["GET", "HEAD", "DELETE"].includes(request.method)) {
    const reader = request.body?.getReader();
    const chunks: Uint8Array[] = [];
    let length = 0;
    if (reader) {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        length += value.byteLength;
        if (length > 10 * 1024 * 1024) {
          await reader.cancel();
          return Response.json({ message: "Request exceeds the 10 MB limit." }, { status: 413 });
        }
        chunks.push(value);
      }
    }
    body = new Uint8Array(length);
    let offset = 0;
    for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.byteLength; }
  }
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);
  const authorization = mode === "local"
    ? `Bearer ${process.env.ROLEREADY_LOCAL_TOKEN || "local-development"}`
    : request.headers.get("authorization");
  if (authorization) headers.set("Authorization", authorization);
  try {
    const response = await fetch(`${process.env.ROLEREADY_API_URL || "http://127.0.0.1:8000"}/${route}`, {
      method: request.method, headers, body: body as BodyInit | undefined, cache: "no-store", redirect: "error",
      signal: AbortSignal.timeout(240_000),
    });
    const outgoing = new Headers({ "Cache-Control": "no-store" });
    for (const key of ["content-type", "content-disposition"]) {
      const value = response.headers.get(key);
      if (value) outgoing.set(key, value);
    }
    return new Response(response.body, { status: response.status, headers: outgoing });
  } catch {
    return Response.json({ code: "backend_unavailable", message: "The practice service could not be reached. Please retry in a moment." }, { status: 503 });
  }
}

export { proxy as GET, proxy as POST, proxy as DELETE };
