/* eslint-disable @typescript-eslint/no-explicit-any */
import axios, {
  type AxiosError,
  type AxiosInstance,
  type InternalAxiosRequestConfig,
  type AxiosResponse,
} from "axios";
import API_CONFIG from "../config/api";
import logger from "../utils/logger";

/**
 * Production-ready Axios client with interceptors.
 * Handles:
 * - Base URL configuration
 * - Request/Response logging
 * - Auth token injection (placeholder)
 * - Global error handling
 */

const apiClient: AxiosInstance = axios.create({
  baseURL: API_CONFIG.BASE_URL,
  timeout: 15000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request Interceptor
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    logger.debug(
      `API Request: ${config.method?.toUpperCase()} ${config.url}`,
      config.data,
    );
    return config;
  },
  (error) => {
    logger.error("API Request Error", error);
    return Promise.reject(error);
  },
);

// Response Interceptor
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    logger.debug(
      `API Response: ${response.status} ${response.config.url}`,
      response.data,
    );
    return response;
  },
  (error: AxiosError) => {
    const status = error.response?.status;
    const message = (error.response?.data as any)?.message || error.message;

    logger.error(`API Error [${status || "NETWORK"}]: ${message}`, {
      url: error.config?.url,
      method: error.config?.method,
      data: error.response?.data,
    });

    // Handle critical status codes
    if (status === 500) {
      logger.error("Critical Server Error detected");
    }

    return Promise.reject(error);
  },
);

export default apiClient;
