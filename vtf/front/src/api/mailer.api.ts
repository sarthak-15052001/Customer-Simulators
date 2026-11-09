import apiClient from "./client";
import { ENDPOINTS } from "./endpoints";
import type { EstimateStayRequestBody } from "./stayEstimate.api";

export type SendSimulationPayload = {
  recipientEmail: string;
  villageName: string;
  nuits: number;
  saison: string;
  dateDebut: string;
  dateFin: string;
  adultes: number;
  formule: string;
  perPersonPerDay: number;
  perDayFamily: number;
  total: number;
  perPerson: number;
  perAdultBase: number;
  totalAdults: number;
  totalChildren: number;
  adhesion: number;
  staySubtotal: number;
  activitiesTotal: number;
  restoTotal: number;
  transportTotal: number;
  hotelEstimate: number;
  hotelSavings: number;
  savingsPct: number;
  formulaIncludes: string;
  childAges: string;
  transportLabel: string;
  bookingUrl: string;
  simulationData: EstimateStayRequestBody;
};

export type SendSimulationResult = {
  success: boolean;
  message?: string;
};

export const mailerApi = {
  sendSimulation: async (
    payload: SendSimulationPayload,
  ): Promise<SendSimulationResult> => {
    const { data } = await apiClient.post<SendSimulationResult>(
      ENDPOINTS.MAILER.SEND_SIMULATION,
      payload,
    );
    return data;
  },
};
