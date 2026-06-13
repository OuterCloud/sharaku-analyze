import { useI18n } from "../i18n/context";

export default function Footer() {
  const { t } = useI18n();

  return (
    <footer className="footer">
      <p>
        {t("footer.dataSource")}
        <a href="https://finance.yahoo.com" target="_blank" rel="noopener noreferrer">
          Yahoo Finance (yfinance)
        </a>
      </p>
      <p className="footer-disclaimer">{t("footer.disclaimer")}</p>
    </footer>
  );
}
