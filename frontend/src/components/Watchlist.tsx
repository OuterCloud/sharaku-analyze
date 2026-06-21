import { useEffect, useState } from "react";
import { useI18n } from "../i18n/context";
import {
  getWatchlist,
  removeFromWatchlist,
  WatchlistItem,
} from "../utils/watchlist";

interface Props {
  onSelect: (ticker: string) => void;
  /** Notify parent when watchlist changes (e.g. item removed) */
  onChange?: () => void;
}

export default function Watchlist({ onSelect, onChange }: Props) {
  const [items, setItems] = useState<WatchlistItem[]>(getWatchlist);
  const { t } = useI18n();

  // Sync with localStorage changes from other components
  useEffect(() => {
    function handleStorage() {
      setItems(getWatchlist());
    }
    window.addEventListener("watchlist-updated", handleStorage);
    return () => window.removeEventListener("watchlist-updated", handleStorage);
  }, []);

  function handleRemove(e: React.MouseEvent, ticker: string) {
    e.stopPropagation();
    const updated = removeFromWatchlist(ticker);
    setItems(updated);
    window.dispatchEvent(new Event("watchlist-updated"));
    onChange?.();
  }

  if (items.length === 0) return null;

  return (
    <div className="watchlist">
      <div className="watchlist-label">{t("watchlist.title")}</div>
      <div className="watchlist-chips">
        {items.map((item) => (
          <button
            key={item.ticker}
            className="watchlist-chip"
            onClick={() => onSelect(item.ticker)}
            title={item.name}
          >
            <span className="watchlist-chip-ticker">{item.ticker}</span>
            <span
              className="watchlist-chip-remove"
              onClick={(e) => handleRemove(e, item.ticker)}
            >
              &times;
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
