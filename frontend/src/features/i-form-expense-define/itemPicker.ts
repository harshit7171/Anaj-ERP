export type ItemPickerRow = {
  id: string;
  itemName: string;
  itemGroup: string;
  itemUnit: string;
  savedDate: string;
};

export function itemDisplayName(row: Record<string, unknown>): string {
  const name = String(row.name ?? "");
  const variety = String(row.variety ?? "").trim();
  return variety ? `${name} ${variety}`.trim() : name;
}

export function parseItemMeta(row: Record<string, unknown>): {
  itemGroup: string;
  itemUnit: string;
} {
  let meta: Record<string, unknown> = {};
  try {
    meta = JSON.parse(String(row.item_metadata_json ?? "{}")) as Record<string, unknown>;
  } catch {
    meta = {};
  }
  const itemGroup = String(meta.item_group ?? "").trim();
  const itemUnit = String(meta.unit ?? meta.rate_per ?? "").trim();
  return {
    itemGroup: itemGroup || String(row.name ?? "").trim(),
    itemUnit,
  };
}

export function formatDateDdMmYyyy(iso: string): string {
  if (!iso || !/^\d{4}-\d{2}-\d{2}/.test(iso)) return iso;
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
}

export function buildItemRows(
  items: Record<string, unknown>[],
  defineDateByItem: Map<string, string>,
): ItemPickerRow[] {
  return items.map((row) => {
    const id = String(row.commodity_id ?? "");
    const meta = parseItemMeta(row);
    return {
      id,
      itemName: itemDisplayName(row),
      itemGroup: meta.itemGroup,
      itemUnit: meta.itemUnit,
      savedDate: defineDateByItem.get(id) ?? "",
    };
  });
}
