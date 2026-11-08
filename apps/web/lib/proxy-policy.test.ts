import { describe, expect, it } from "vitest";
import { originError } from "./proxy-policy";

const local = { url: "http://localhost:3100/api/backend/v1/extract", host: "127.0.0.1:3100", origin: "http://127.0.0.1:3100", mode: "local" };
describe("proxy origin checks", () => {
  it("accepts the actual browser origin when Next normalizes its internal URL", () => {
    expect(originError(local)).toBeNull();
  });
  it("rejects a different origin and DNS-rebinding hosts in local mode", () => {
    expect(originError({ ...local, origin: "https://another-site.example" })).not.toBeNull();
    expect(originError({ ...local, host: "another-site.example", origin: "http://another-site.example" })).not.toBeNull();
    expect(originError({ ...local, host: "evil@localhost:3100", origin: null })).not.toBeNull();
  });
  it("requires production authentication and an explicit public origin", () => {
    expect(originError({ ...local, environment: "production" })).not.toBeNull();
    expect(originError({ ...local, environment: "production", mode: "supabase" })).not.toBeNull();
  });
  it("accepts the configured HTTPS origin behind a reverse proxy", () => {
    expect(originError({ ...local, mode: "supabase", environment: "production", webOrigin: "https://app.example.com", origin: "https://app.example.com", host: "app.example.com" })).toBeNull();
    expect(originError({ ...local, mode: "supabase", environment: "production", webOrigin: "https://app.example.com", origin: "https://other.example.com", host: "app.example.com" })).not.toBeNull();
  });
});
