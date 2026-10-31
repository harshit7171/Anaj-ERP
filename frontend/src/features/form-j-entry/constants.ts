import type { LookupItem } from "../../Autocomplete";

export type DheriRow = {
  rowId: number;
  commodity: LookupItem | null;
  purchaser: LookupItem | null;
  gpNo: string;
  bags: string;
  pack: string;
  extra: string;
  rate: string;
};

export function newDheriRow(rowId: number): DheriRow {
  return {
    rowId,
    commodity: null,
    purchaser: null,
    gpNo: "",
    bags: "",
    pack: "50",
    extra: "",
    rate: "",
  };
}

/** Quintals from bags × pack (kg) + extra kg. */
export function formJQuantity(row: DheriRow): number {
  const kilograms = Number(row.bags || 0) * Number(row.pack || 0) + Number(row.extra || 0);
  return kilograms / 100;
}

export function defaultDueDateIso(daysAhead = 15): string {
  const value = new Date();
  value.setDate(value.getDate() + daysAhead);
  return value.toISOString().slice(0, 10);
}

export function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}
