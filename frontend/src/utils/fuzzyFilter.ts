function normalize(value: string): string {
  return value.toLowerCase().replace(/\s+/g, " ").trim();
}

export function fuzzyMatch(query: string, target: string): boolean {
  const cleanQuery = normalize(query);
  if (!cleanQuery) return true;
  const cleanTarget = normalize(target);
  const tokens = cleanQuery.split(" ");
  return tokens.every((token) => cleanTarget.includes(token));
}

export function debounce<T extends (...args: never[]) => void>(
  fn: T,
  delayMs: number,
): (...args: Parameters<T>) => void {
  let timer: number | undefined;
  return (...args: Parameters<T>) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => fn(...args), delayMs);
  };
}
