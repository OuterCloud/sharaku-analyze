const CACHE_TTL = 60 * 60 * 1000; // 1 hour (same as backend)

interface CacheEntry<T> {
  data: T;
  ts: number;
}

function cacheKey(prefix: string, ...args: string[]): string {
  return `sharaku_cache:${prefix}:${args.join(":")}`;
}

export function getCached<T>(prefix: string, ...args: string[]): T | null {
  try {
    const raw = sessionStorage.getItem(cacheKey(prefix, ...args));
    if (!raw) return null;
    const entry: CacheEntry<T> = JSON.parse(raw);
    if (Date.now() - entry.ts > CACHE_TTL) {
      sessionStorage.removeItem(cacheKey(prefix, ...args));
      return null;
    }
    return entry.data;
  } catch {
    return null;
  }
}

export function setCache<T>(data: T, prefix: string, ...args: string[]): void {
  try {
    const entry: CacheEntry<T> = { data, ts: Date.now() };
    sessionStorage.setItem(cacheKey(prefix, ...args), JSON.stringify(entry));
  } catch {
    // sessionStorage full or unavailable - silently ignore
  }
}
