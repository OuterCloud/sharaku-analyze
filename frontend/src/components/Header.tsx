import { useI18n } from "../i18n/context";
import { useTheme } from "../theme/context";

export default function Header() {
  const { theme, toggle } = useTheme();
  const { lang, setLang, t } = useI18n();

  return (
    <header className="header">
      <div className="header-top">
        <h1 className="header-title">Sharaku Analyze</h1>
        <div className="header-actions">
          <button
            className="header-btn"
            onClick={toggle}
            aria-label="Toggle theme"
          >
            {theme === "light" ? "\u263D" : "\u2600"}
          </button>
          <button
            className="header-btn"
            onClick={() => setLang(lang === "zh" ? "en" : "zh")}
            aria-label="Toggle language"
          >
            {lang === "zh" ? "EN" : "中"}
          </button>
        </div>
      </div>
      <p className="header-subtitle">{t("header.subtitle")}</p>
    </header>
  );
}
