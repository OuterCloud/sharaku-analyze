const STORAGE_KEY = "sharaku_watchlist";

export interface WatchlistItem {
  ticker: string;
  name: string;
}

export function getWatchlist(): WatchlistItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function addToWatchlist(item: WatchlistItem): WatchlistItem[] {
  const list = getWatchlist();
  if (list.some((i) => i.ticker === item.ticker)) return list;
  const updated = [...list, item];
  localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  return updated;
}

export function removeFromWatchlist(ticker: string): WatchlistItem[] {
  const list = getWatchlist().filter((i) => i.ticker !== ticker);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  return list;
}

export function isInWatchlist(ticker: string): boolean {
  return getWatchlist().some((i) => i.ticker === ticker);
}
