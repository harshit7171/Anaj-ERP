export type NoteLine = {
  account_id: string;
  account_name: string;
  particulars: string;
  amount: string;
};

export function emptyNoteLine(): NoteLine {
  return { account_id: "", account_name: "", particulars: "", amount: "" };
}

export function withTrailingBlankLine(lines: NoteLine[]): NoteLine[] {
  const copy = [...lines];
  const last = copy[copy.length - 1];
  if (last?.account_name.trim() || last?.amount.trim()) copy.push(emptyNoteLine());
  else if (!copy.length) copy.push(emptyNoteLine());
  return copy;
}

export function parseNoteLines(raw: unknown): NoteLine[] {
  if (!Array.isArray(raw) || !raw.length) return [emptyNoteLine()];
  return withTrailingBlankLine(
    raw.map((row) => {
      const item = row as Record<string, unknown>;
      return {
        account_id: String(item.account_id ?? ""),
        account_name: String(item.account_name ?? ""),
        particulars: String(item.particulars ?? ""),
        amount: String(item.amount ?? ""),
      };
    }),
  );
}

export function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}

export function ddMmYyyyToIso(value: string): string {
  const trimmed = value.trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return trimmed;
  const match = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(trimmed);
  if (!match) return trimmed;
  const [, d, m, y] = match;
  return `${y}-${m.padStart(2, "0")}-${d.padStart(2, "0")}`;
}

export function isoToDdMmYyyy(iso: string): string {
  if (!iso || !/^\d{4}-\d{2}-\d{2}/.test(iso)) return iso;
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
}
