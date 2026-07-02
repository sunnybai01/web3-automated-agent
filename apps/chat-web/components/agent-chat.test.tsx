import React from "react";
import { renderToString } from "react-dom/server";
import { expect, it, vi } from "vitest";

vi.mock("@copilotkit/react-core/v2", () => ({
  useFrontendTool: () => undefined,
}));

vi.mock("@copilotkit/react-ui", () => ({
  CopilotChat: () => <div>Copilot Chat Mock</div>,
}));

import AgentChat from "./agent-chat";
import { normalizeAnalysisTargetInput } from "./agent-chat";
import { shouldRequestTabData } from "./agent-chat";

it("renders dashboard-first workspace", () => {
  const html = renderToString(<AgentChat />);
  expect(html).toContain("Active Opportunities");
  expect(html).toContain("Source Health");
  expect(html).toContain("Schedule Logs");
  expect(html).toContain("Source Trust");
  expect(html).toContain("Trust");
  expect(html).toContain("Run Scan");
});

it("prefers a specific event id over free-form tool filters", () => {
  expect(
    normalizeAnalysisTargetInput(
      {
        eventId: 3,
        sourceName: "Solana Foundation",
        from: "superteam.fun",
        to: "superteam.fun",
        limit: 5,
      },
      9
    )
  ).toEqual({ event_id: 3 });
});

it("keeps source queries only when the date range is ISO-like", () => {
  expect(
    normalizeAnalysisTargetInput({
      sourceName: "Solana Foundation",
      from: "2026-07-01",
      to: "2026-07-02T00:00:00Z",
      limit: 999,
    })
  ).toEqual({
    source_name: "Solana Foundation",
    from: "2026-07-01",
    to: "2026-07-02T00:00:00Z",
    limit: 100,
  });
});

it("requests tab data when the panel is empty or previously failed", () => {
  expect(
    shouldRequestTabData({
      hasData: false,
      isLoading: false,
      hasError: false,
    })
  ).toBe(true);

  expect(
    shouldRequestTabData({
      hasData: true,
      isLoading: false,
      hasError: true,
    })
  ).toBe(true);

  expect(
    shouldRequestTabData({
      hasData: true,
      isLoading: false,
      hasError: false,
    })
  ).toBe(false);

  expect(
    shouldRequestTabData({
      hasData: false,
      isLoading: true,
      hasError: true,
    })
  ).toBe(false);
});
