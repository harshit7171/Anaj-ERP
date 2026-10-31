import { useMemo, useState } from "react";

import { debounce, fuzzyMatch } from "../utils/fuzzyFilter";
import SortableTable, { type SortableColumn } from "./SortableTable";

export type ModifySearchRow = {
  document_id: string;
  document_number: string;
  document_date: string;
  party_name?: string;
  village_name?: string;
  reference_number?: string;
  grand_total_paise?: number;
};

function ModifyRecordSearchBar({
  rows,
  loading,
  onQueryChange,
  onSelect,
}: {
  rows: ModifySearchRow[];
  loading?: boolean;
  onQueryChange(query: string): void;
  onSelect(row: ModifySearchRow): void;
}) {
  const [localQuery, setLocalQuery] = useState("");
  const debouncedNotify = useMemo(
    () => debounce((value: string) => onQueryChange(value), 280),
    [onQueryChange],
  );

  const columns: SortableColumn<ModifySearchRow>[] = [
    { key: "document_date", label: "Date", sortValue: (r) => r.document_date },
    { key: "document_number", label: "Bill No", sortValue: (r) => r.document_number },
    { key: "party_name", label: "Party", sortValue: (r) => r.party_name ?? "" },
    { key: "village_name", label: "Village", sortValue: (r) => r.village_name ?? "" },
    { key: "reference_number", label: "Marka / Ref", sortValue: (r) => r.reference_number ?? "" },
  ];

  const filtered = rows.filter((row) => {
    const haystack = [
      row.document_number,
      row.party_name,
      row.village_name,
      row.reference_number,
    ].join(" ");
    return fuzzyMatch(localQuery, haystack);
  });

  return (
    <div className="modify-search-bar">
      <label className="modify-search-label">
        Search / Select Name
        <input
          autoFocus
          className="modify-search-input"
          placeholder="Party, village, marka, bill no…"
          value={localQuery}
          onChange={(event) => {
            setLocalQuery(event.target.value);
            debouncedNotify(event.target.value);
          }}
        />
      </label>
      {loading && <p className="text-[10px] text-[#64748b]">Searching…</p>}
      <SortableTable
        columns={columns}
        defaultSortKey="document_date"
        defaultDescending
        rows={filtered}
        onRowClick={onSelect}
        rowKey={(row) => row.document_id}
        renderCell={(row, key) => {
          if (key === "grand_total_paise") {
            return `₹${((row.grand_total_paise ?? 0) / 100).toFixed(2)}`;
          }
          return String(row[key as keyof ModifySearchRow] ?? "—");
        }}
      />
    </div>
  );
}

export default ModifyRecordSearchBar;
