import client from "./client";
import ENDPOINTS from "./endpoints";

export type ApiFormule = {
  code: string;
  icon: string;
  iconKey: string;
  label: string;
  shortDescription: string;
  text?: string;
  sortOrder: number;
};

export const getFormules = async (): Promise<ApiFormule[]> => {
  const result = await client.get<{ data: ApiFormule[] }>(ENDPOINTS.FORMULES);
  return result.data.data;
};

export default { getFormules };
