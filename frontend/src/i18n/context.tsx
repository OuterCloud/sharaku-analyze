import { createContext, useContext, useState, ReactNode } from "react";
import zh, { TranslationKey } from "./zh";
import en from "./en";

type Lang = "zh" | "en";

interface I18nContextValue {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: TranslationKey) => string;
}

const dictMap: Record<Lang, Record<TranslationKey, string>> = { zh, en };

const I18nContext = createContext<I18nContextValue>({
  lang: "zh",
  setLang: () => {},
  t: (key) => key,
});

function getInitialLang(): Lang {
  const stored = localStorage.getItem("lang");
  if (stored === "zh" || stored === "en") return stored;
  return navigator.language.startsWith("zh") ? "zh" : "en";
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(getInitialLang);

  function setLang(l: Lang) {
    setLangState(l);
    localStorage.setItem("lang", l);
  }

  function t(key: TranslationKey): string {
    return dictMap[lang][key] || key;
  }

  return (
    <I18nContext.Provider value={{ lang, setLang, t }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  return useContext(I18nContext);
}
