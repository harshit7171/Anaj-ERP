import type { KeyboardEvent, ReactNode } from "react";

import { useGridEnterNavigation } from "../hooks/useGridEnterNavigation";

function DataGrid({
  children,
  className = "",
  onRowComplete,
  onKeyDown,
}: {
  children: ReactNode;
  className?: string;
  onRowComplete?(): void;
  onKeyDown?(event: KeyboardEvent<HTMLTableElement>): void;
}) {
  const handleEnter = useGridEnterNavigation(onRowComplete);

  return (
    <div className={`transaction-grid-shell ${className}`.trim()}>
      <table
        className="w-full table-fixed border-collapse font-mono text-xs tracking-tight tabular-nums"
        onKeyDown={(event) => {
          handleEnter(event as KeyboardEvent<HTMLElement>);
          onKeyDown?.(event);
        }}
      >
        {children}
      </table>
    </div>
  );
}

export default DataGrid;
