import * as React from "react";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import ErrorOutlineRoundedIcon from "@mui/icons-material/ErrorOutlineRounded";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import WarningAmberRoundedIcon from "@mui/icons-material/WarningAmberRounded";
import { Box } from "./Box";
import { IconButton } from "./IconButton";
import { Typography } from "./Typography";

export type ToastVariant = "success" | "error" | "warning" | "info";

export type ToastInput = {
  variant: ToastVariant;
  message: string;
  duration?: number;
};

type ToastItem = ToastInput & { id: string };

type ToastContextValue = {
  show: (toast: ToastInput) => void;
  success: (message: string) => void;
  error: (message: string) => void;
  warning: (message: string) => void;
  info: (message: string) => void;
};

const ToastContext = React.createContext<ToastContextValue | null>(null);

const DEFAULT_DURATION_MS = 4200;

const variantStyles: Record<
  ToastVariant,
  {
    icon: React.ReactNode;
    border: string;
    background: string;
    iconColor: string;
  }
> = {
  success: {
    icon: <CheckCircleRoundedIcon sx={{ fontSize: 22 }} />,
    border: "rgba(46, 125, 50, 0.22)",
    background:
      "linear-gradient(135deg, rgba(174,218,196,0.42) 0%, rgba(255,255,255,0.96) 100%)",
    iconColor: "var(--vtf-green)",
  },
  error: {
    icon: <ErrorOutlineRoundedIcon sx={{ fontSize: 22 }} />,
    border: "rgba(224, 138, 102, 0.35)",
    background:
      "linear-gradient(135deg, rgba(242,166,128,0.22) 0%, rgba(255,255,255,0.97) 100%)",
    iconColor: "var(--vtf-orange-dark)",
  },
  warning: {
    icon: <WarningAmberRoundedIcon sx={{ fontSize: 22 }} />,
    border: "rgba(0, 68, 90, 0.14)",
    background:
      "linear-gradient(135deg, rgba(252,249,246,0.98) 0%, rgba(255,255,255,0.96) 100%)",
    iconColor: "var(--vtf-navy)",
  },
  info: {
    icon: <InfoOutlinedIcon sx={{ fontSize: 22 }} />,
    border: "rgba(0, 168, 181, 0.22)",
    background:
      "linear-gradient(135deg, rgba(0,168,181,0.1) 0%, rgba(255,255,255,0.96) 100%)",
    iconColor: "var(--vtf-teal)",
  },
};

function ToastCard({
  toast,
  onDismiss,
}: {
  toast: ToastItem;
  onDismiss: (id: string) => void;
}) {
  const style = variantStyles[toast.variant];

  const isError = toast.variant === "error";

  return (
    <Box
      role={isError ? "alert" : "status"}
      aria-live={isError ? "assertive" : "polite"}
      sx={{
        display: "flex",
        alignItems: "flex-start",
        gap: 1.25,
        width: "min(100vw - 24px, 400px)",
        minWidth: { xs: "min(100%, 280px)", sm: 300 },
        p: 1.625,
        pr: 0.75,
        borderRadius: "20px",
        border: `1px solid ${style.border}`,
        background: style.background,
        backdropFilter: "blur(14px)",
        WebkitBackdropFilter: "blur(14px)",
        boxShadow: `
          0 4px 6px -1px rgba(0, 68, 90, 0.06),
          0 22px 50px -12px rgba(0, 68, 90, 0.18)
        `,
        animation: "vtf-toast-in 0.32s cubic-bezier(0.22, 1, 0.36, 1)",
      }}
    >
      <Box
        sx={{
          color: style.iconColor,
          mt: 0.125,
          flexShrink: 0,
          width: 36,
          height: 36,
          borderRadius: "12px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          bgcolor: "rgba(255,255,255,0.55)",
          border: "1px solid rgba(255,255,255,0.65)",
        }}
      >
        {style.icon}
      </Box>
      <Typography
        sx={{
          flex: 1,
          fontSize: "var(--vtf-font-sm)",
          fontWeight: 800,
          lineHeight: 1.5,
          letterSpacing: "-0.01em",
          color: "var(--vtf-navy)",
          pt: 0.35,
          pr: 0.25,
        }}
      >
        {toast.message}
      </Typography>
      <IconButton
        size="small"
        aria-label="Close"
        onClick={() => onDismiss(toast.id)}
        sx={{
          color: "rgba(0,68,90,0.42)",
          mt: -0.125,
          mr: -0.25,
          "&:hover": {
            color: "var(--vtf-navy)",
            bgcolor: "rgba(0,68,90,0.07)",
          },
        }}
      >
        <CloseRoundedIcon sx={{ fontSize: "var(--vtf-font-lg)" }} />
      </IconButton>
    </Box>
  );
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<ToastItem[]>([]);
  const timersRef = React.useRef<Map<string, number>>(new Map());

  const dismiss = React.useCallback((id: string) => {
    const timer = timersRef.current.get(id);
    if (timer != null) {
      window.clearTimeout(timer);
      timersRef.current.delete(id);
    }
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const show = React.useCallback(
    ({ variant, message, duration = DEFAULT_DURATION_MS }: ToastInput) => {
      const id =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `${Date.now()}-${Math.random()}`;

      setToasts((prev) => [
        ...prev.slice(-4),
        { id, variant, message, duration },
      ]);

      const timer = window.setTimeout(() => dismiss(id), duration);
      timersRef.current.set(id, timer);
    },
    [dismiss],
  );

  const value = React.useMemo<ToastContextValue>(
    () => ({
      show,
      success: (message) => show({ variant: "success", message }),
      error: (message) => show({ variant: "error", message }),
      warning: (message) => show({ variant: "warning", message }),
      info: (message) => show({ variant: "info", message }),
    }),
    [show],
  );

  React.useEffect(() => {
    const timers = timersRef.current;
    return () => {
      timers.forEach((timer) => window.clearTimeout(timer));
      timers.clear();
    };
  }, []);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <Box
        className="vtf-toast-region"
        aria-label="Notifications"
        sx={{
          position: "fixed",
          top: {
            xs: "calc(12px + env(safe-area-inset-top, 0px))",
            sm: "calc(16px + env(safe-area-inset-top, 0px))",
          },
          right: {
            xs: "calc(12px + env(safe-area-inset-right, 0px))",
            sm: "calc(20px + env(safe-area-inset-right, 0px))",
          },
          zIndex: 2000,
          display: "flex",
          flexDirection: "column-reverse",
          alignItems: "flex-end",
          gap: 1.25,
          maxHeight: {
            xs: "calc(100dvh - 24px - env(safe-area-inset-top, 0px))",
            sm: "calc(100dvh - 32px - env(safe-area-inset-top, 0px))",
          },
          overflowY: "auto",
          overflowX: "hidden",
          scrollbarWidth: "thin",
          pointerEvents: "none",
          "& > *": { pointerEvents: "auto" },
        }}
      >
        {toasts.map((toast) => (
          <ToastCard key={toast.id} toast={toast} onDismiss={dismiss} />
        ))}
      </Box>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = React.useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return ctx;
}
