import { afterEach, expect, it, vi } from "vitest";

import { DELETE } from "./route";

afterEach(() => {
  vi.restoreAllMocks();
});

it("proxies delete requests with the resolved dynamic event id", async () => {
  process.env.CHAT_API_BASE_URL = "http://backend.test";
  process.env.CHAT_API_INTERNAL_KEY = "secret";

  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
    json: async () => ({ status: "success", event_id: 42, deleted: true }),
    status: 200,
  } as Response);

  const response = await DELETE(new Request("http://localhost"), {
    params: Promise.resolve({ eventId: "42" }),
  });

  expect(fetchMock).toHaveBeenCalledWith(
    "http://backend.test/api/v1/dashboard/opportunities/42",
    {
      method: "DELETE",
      headers: {
        "x-internal-key": "secret",
      },
      cache: "no-store",
    }
  );
  expect(response.status).toBe(200);
  await expect(response.json()).resolves.toEqual({
    status: "success",
    event_id: 42,
    deleted: true,
  });
});
