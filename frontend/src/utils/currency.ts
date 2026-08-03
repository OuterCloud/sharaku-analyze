/**
 * 根据 ticker 后缀判断货币符号
 */
export function getCurrencySymbol(ticker: string): string {
  if (ticker.endsWith(".SS") || ticker.endsWith(".SZ")) return "¥";
  if (ticker.endsWith(".HK")) return "HK$";
  if (ticker.endsWith(".T")) return "¥";
  if (ticker.endsWith(".TW") || ticker.endsWith(".TWO")) return "NT$";
  if (ticker.endsWith(".KS") || ticker.endsWith(".KQ")) return "₩";
  if (ticker.endsWith(".L")) return "£";
  if (ticker.endsWith(".PA") || ticker.endsWith(".F")) return "€";
  if (ticker.endsWith(".AX")) return "A$";
  if (ticker.endsWith(".TO")) return "C$";
  if (ticker.endsWith(".SI")) return "S$";
  return "$";
}

/**
 * 格式化价格（带货币符号）
 */
export function formatPrice(price: number, ticker: string): string {
  const symbol = getCurrencySymbol(ticker);
  return `${symbol}${price.toFixed(2)}`;
}
