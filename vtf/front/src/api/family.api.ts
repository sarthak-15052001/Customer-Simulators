import apiClient from "./client";
import { ENDPOINTS } from "./endpoints";

/** Request body for `POST /family/qf` (`QfInputSerializer`). */
export type FamilyQfInput = {
  netMonthlyIncome: number;
  parts: number;
};

/** Core payload; API may wrap as `{ success, message, data: { qfVal, badge } }`. */
export type FamilyQfOutput = {
  qfVal: number;
  badge: string;
};

function parseQfPayload(data: unknown): FamilyQfOutput {
  let node: unknown = data;
  if (node && typeof node === "object" && "data" in node) {
    node = (node as { data: unknown }).data;
  }
  if (!node || typeof node !== "object") {
    throw new Error("Invalid family QF response");
  }
  const row = node as Record<string, unknown>;
  const qfVal = Number(row.qfVal);
  const badge = String(row.badge ?? "");
  if (!Number.isFinite(qfVal)) {
    throw new Error("Invalid family QF response");
  }
  return { qfVal, badge };
}

export const familyApi = {
  postFamilyQf: async (body: FamilyQfInput): Promise<FamilyQfOutput> => {
    const { data } = await apiClient.post<unknown>(
      ENDPOINTS.PRICING.FAMILY_QF,
      {
        netMonthlyIncome: body.netMonthlyIncome,
        parts: body.parts,
      },
    );
    return parseQfPayload(data);
  },
};

export default familyApi;
