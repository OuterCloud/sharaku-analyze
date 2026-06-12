export default function Footer() {
  return (
    <footer className="footer">
      <p>
        数据来源：<a href="https://finance.yahoo.com" target="_blank" rel="noopener noreferrer">Yahoo Finance (yfinance)</a>
      </p>
      <p className="footer-disclaimer">
        预测结果仅供参考，不构成投资建议。投资有风险，入市需谨慎。
      </p>
    </footer>
  );
}
