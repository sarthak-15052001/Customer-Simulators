import apiClient from "./client";
import { ENDPOINTS } from "./endpoints";
import type { ChildDiscountsRow } from "../utils/familyTab";

export type { ChildDiscountsRow } from "../utils/familyTab";

/** `payload` from `GET /pricing-rules` (subset typed for the front). */
export type PricingRulesPayload = {
  durationCoefficients?: Record<string, number>;
  formulaCoefficients?: Record<string, number>;
  membership?: { individual: number; familyOrCouple: number };
  soloSupplementPerNight?: Record<string, number>;
  quinzaineFuteeRate?: number;
  maxiFamilyChildrenRate?: number;
  defaults?: Record<string, number>;
  childDiscounts: ChildDiscountsRow;
};

export type PricingRulesApiResponse = {
  updatedAt: string;
  payload: PricingRulesPayload;
};

function unwrapEnvelope(data: unknown): unknown {
  if (!data || typeof data !== "object") return data;
  const o = data as Record<string, unknown>;
  if ("data" in o && o.data != null && typeof o.data === "object") {
    return o.data;
  }
  return data;
}

export function parsePricingRulesResponse(data: unknown): PricingRulesApiResponse {
  const node = unwrapEnvelope(data);
  if (!node || typeof node !== "object") {
    throw new Error("Invalid pricing rules response");
  }
  const row = node as Record<string, unknown>;
  const updatedAt =
    typeof row.updatedAt === "string"
      ? row.updatedAt
      : typeof row.updated_at === "string"
        ? row.updated_at
        : "";
  const payload = row.payload;
  if (!payload || typeof payload !== "object") {
    throw new Error("Invalid pricing rules response: missing payload");
  }
  const p = payload as Record<string, unknown>;
  const cd = p.childDiscounts;
  if (!cd || typeof cd !== "object") {
    throw new Error("Invalid pricing rules payload: missing childDiscounts");
  }
  return {
    updatedAt,
    payload: payload as PricingRulesPayload,
  };
}

export const pricingRulesApi = {
  getPricingRules: async (): Promise<PricingRulesApiResponse> => {
    const { data } = await apiClient.get<unknown>(ENDPOINTS.PRICING_RULES);
    return parsePricingRulesResponse(data);
  },
};

export default pricingRulesApi;
