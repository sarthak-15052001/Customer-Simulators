/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * Production-ready logger for the VTF Simulator.
 * Features:
 * - Environment-aware logging (disabled or reduced in production if desired)
 * - Structured logging for better debugging
 * - Support for error reporting services (placeholders)
 */

type LogLevel = "info" | "warn" | "error" | "debug";

const IS_PROD = import.meta.env.PROD;

class Logger {
  private formatMessage(level: LogLevel, message: string) {
    const timestamp = new Date().toISOString();
    return `[${timestamp}] [${level.toUpperCase()}] ${message}`;
  }

  debug(message: string, data?: any) {
    if (!IS_PROD) {
      console.debug(this.formatMessage("debug", message), data || "");
    }
  }

  info(message: string, data?: any) {
    console.info(this.formatMessage("info", message), data || "");
  }

  warn(message: string, data?: any) {
    console.warn(this.formatMessage("warn", message), data || "");
    // In production, you might want to send warnings to a monitoring service
  }

  error(message: string, error?: any) {
    console.error(this.formatMessage("error", message), error || "");

    // Production error reporting logic
    if (IS_PROD) {
      this.reportToService();
    }
  }

  private reportToService() {
    // Placeholder for Sentry, LogRocket, or similar services
    // console.log('Reporting error to production monitoring service...');
  }
}

export const logger = new Logger();
export default logger;
