import React from "react";
import { renderToString } from "react-dom/server";
import { expect, it } from "vitest";

import ResultPanels from "./result-panels";

it("renders investigation insight when investigation data is present", () => {
  const html = renderToString(
    <ResultPanels
      data={{
        selected: { target_event_ids: [42] },
        verification: {
          score: 82,
          level: "high",
          verdict: "trusted",
          evidence: [],
          unknowns: [],
          conflicts: [],
        },
        options: { options: [] },
      }}
      investigation={{
        status: "completed",
        event_id: 42,
        mission: {
          id: 7,
          goal: "investigate_event:42",
          event_id: 42,
          status: "completed",
          mission_type: "single_event_investigation",
          max_steps: 5,
        },
        conclusion: {
          event_id: 42,
          title: "Base Builder Rewards",
          verdict: "verified",
          recommended_action: "promote",
          summary: "Verification verdict for event 42: verified.",
          similar_events: [
            {
              event_id: 2,
              title: "Base Ecosystem Grants",
              ecosystem: "base",
              similarity: 0.88,
            },
          ],
          supporting_evidence: {
            url: "https://apply.base.org",
            title: "Base Builder Rewards",
            excerpt: "Applications are open for Base builders.",
          },
        },
        error: "",
        trajectory: [
          {
            step_index: 0,
            action: "load_event",
            thought: "Load the requested event before choosing tools.",
            action_input: { event_id: 42 },
            observation: { title: "Base Builder Rewards" },
          },
          {
            step_index: 1,
            action: "verify_event",
            thought:
              "Use the deterministic verifier before producing a conclusion.",
            action_input: { event_type: "grant" },
            observation: { verdict: "verified" },
          },
        ],
      }}
    />
  );

  expect(html).toContain("Investigation Insight");
  expect(html).toContain("promote");
  expect(html).toContain("Base Ecosystem Grants");
  expect(html).toContain("Applications are open for Base builders.");
  expect(html).toContain("Mission Trajectory");
  expect(html).toContain("Load Event");
  expect(html).toContain("Verification");
  expect(html).toContain(
    "Loaded the selected opportunity from the event store."
  );
});
