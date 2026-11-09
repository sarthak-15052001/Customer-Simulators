/* eslint-disable react-hooks/set-state-in-effect */
import * as React from "react";
import { LocaleLoadingScreen } from "../components/shared/LocaleLoadingScreen";
import {
  loadLocale,
  resolveTranslation,
  type Language,
  type TranslationObject,
} from "../locales/loadLocale";

const DEFAULT_LANGUAGE: Language = "FR";

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (path: string, fallback?: string) => string;
  isLocaleLoading: boolean;
}

const LanguageContext = React.createContext<LanguageContextType | undefined>(
  undefined,
);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguage] = React.useState<Language>(DEFAULT_LANGUAGE);
  const [messages, setMessages] = React.useState<TranslationObject | null>(
    null,
  );
  const [isLocaleLoading, setIsLocaleLoading] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;
    setIsLocaleLoading(true);

    void loadLocale(language).then((data) => {
      if (!cancelled) {
        setMessages(data);
        setIsLocaleLoading(false);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [language]);

  const t = React.useCallback(
    (path: string, fallback?: string): string => {
      if (!messages) return fallback ?? path;
      return resolveTranslation(messages, path, fallback);
    },
    [messages],
  );

  const value = React.useMemo(
    () => ({ language, setLanguage, t, isLocaleLoading }),
    [language, t, isLocaleLoading],
  );

  if (!messages) {
    return <LocaleLoadingScreen />;
  }

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useTranslation() {
  const context = React.useContext(LanguageContext);
  if (context === undefined) {
    throw new Error("useTranslation must be used within a LanguageProvider");
  }
  return context;
}

export type { Language };
