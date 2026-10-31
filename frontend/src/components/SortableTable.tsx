import { useMemo, useState } from "react";

export type SortableColumn<T> = {
  key: string;
  label: string;
  sortValue(row: T): string | number;
};

function SortableTable<T>({
  columns,
  rows,
  rowKey,
  renderCell,
  onRowClick,
  defaultSortKey,
  defaultDescending = true,
}: {
  columns: SortableColumn<T>[];
  rows: T[];
  rowKey(row: T): string;
  renderCell(row: T, key: string): string;
  onRowClick?(row: T): void;
  defaultSortKey: string;
  defaultDescending?: boolean;
}) {
  const [sortKey, setSortKey] = useState(defaultSortKey);
  const [descending, setDescending] = useState(defaultDescending);

  const sorted = useMemo(() => {
    const column = columns.find((item) => item.key === sortKey) ?? columns[0];
    const copy = [...rows];
    copy.sort((left, right) => {
      const a = column.sortValue(left);
      const b = column.sortValue(right);
      if (a === b) return 0;
      if (a < b) return descending ? 1 : -1;
      return descending ? -1 : 1;
    });
    return copy;
  }, [columns, descending, rows, sortKey]);

  function toggleSort(key: string) {
    if (sortKey === key) {
      setDescending((current) => !current);
      return;
    }
    setSortKey(key);
    setDescending(true);
  }

  return (
    <div className="sortable-table-shell">
      <table className="sortable-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key}>
                <button
                  className="sortable-th"
                  type="button"
                  onClick={() => toggleSort(column.key)}
                >
                  {column.label}
                  {sortKey === column.key ? (descending ? " ▼" : " ▲") : ""}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr
              className={onRowClick ? "sortable-row-clickable" : undefined}
              key={rowKey(row)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
            >
              {columns.map((column) => (
                <td key={column.key}>{renderCell(row, column.key)}</td>
              ))}
            </tr>
          ))}
          {!sorted.length && (
            <tr>
              <td colSpan={columns.length} className="text-center text-[#64748b]">
                No matching records.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default SortableTable;
