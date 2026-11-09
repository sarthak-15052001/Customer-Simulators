/**
 * Centralized API configuration for the VTF Simulator.
 * Backend host is managed via environment variables.
 */

const API_HOST = import.meta.env.VITE_API_URL;
const API_BASE_URL = `${API_HOST}/api/v1`;

export const API_CONFIG = {
  HOST: API_HOST,
  BASE_URL: API_BASE_URL,
} as const;

export default API_CONFIG;
