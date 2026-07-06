import type { InvestigationResponse } from "../types/chat";

type InvestigationApi = {
  investigate: (input: { event_id: number }) => Promise<InvestigationResponse>;
};

export async function runInvestigation(
  api: InvestigationApi,
  eventId: number
): Promise<InvestigationResponse> {
  return api.investigate({ event_id: eventId });
}
