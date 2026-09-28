import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, formatDetail } from "../api.js";

afterEach(() => vi.restoreAllMocks());

function mockFetch(response) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(response);
}

const json = (body, init = {}) =>
  new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" }, ...init });

describe("formatDetail", () => {
  it("passes strings through", () => {
    expect(formatDetail("Not found", "x")).toBe("Not found");
  });
  it("joins FastAPI validation messages", () => {
    const detail = [{ loc: ["body", "body"], msg: "Pitch body must not be empty" }, { msg: "second" }];
    expect(formatDetail(detail, "x")).toBe("Pitch body must not be empty; second");
  });
  it("falls back when there is no detail", () => {
    expect(formatDetail(undefined, "Bad Request")).toBe("Bad Request");
  });
});

describe("api", () => {
  it("builds query strings and skips empty filters", async () => {
    const spy = mockFetch(json([]));
    await api.listOpportunities({ verdict: "pass", status: "", q: "abc" });
    expect(spy.mock.calls[0][0]).toMatch(/\/opportunities\?verdict=pass&q=abc$/);
  });

  it("sends status changes as PATCH", async () => {
    const spy = mockFetch(json({ id: 1 }));
    await api.setStatus(1, "rejected");
    const [url, options] = spy.mock.calls[0];
    expect(url).toMatch(/\/opportunities\/1$/);
    expect(options.method).toBe("PATCH");
    expect(JSON.parse(options.body)).toEqual({ status: "rejected" });
  });

  it("raises an ApiError carrying the server message", async () => {
    mockFetch(json({ detail: "Opportunity not found" }, { status: 404, statusText: "Not Found" }));
    await expect(api.getOpportunity(9)).rejects.toMatchObject({ status: 404, message: "Opportunity not found" });
  });

  it("explains when the backend is unreachable", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    const error = await api.listCompanies().catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.message).toMatch(/Cannot reach the API/);
  });
});
