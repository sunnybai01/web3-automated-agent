import { expect, it } from "vitest";

import { runMixedModeVerification } from "./actions";

it("executes select -> verify -> propose chain", async () => {
  const api = {
    selectTargets: async () => ({ target_event_ids: [11] }),
    verify: async () => ({
      score: 82,
      level: "high",
      verdict: "trusted",
      evidence: [],
      unknowns: [],
      conflicts: [],
    }),
    proposeOptions: async () => ({
      options: [{ tier: "light", summary: "x", assumptions: [] }],
    }),
  };

  const result = await runMixedModeVerification(api, { event_id: 11 });
  expect(result.verification.score).toBe(82);
  expect(result.options.options.length).toBe(1);
  expect(result.options.options[0]?.tier).toBe("light");
});
