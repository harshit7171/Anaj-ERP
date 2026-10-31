import { KeyboardEvent, useEffect, useRef, useState } from "react";

type LookupItem = {
  id: string;
  label: string;
  address?: string;
  gstin?: string;
  phone?: string;
  account_id?: string;
  account_name?: string;
  related_name?: string;
};

type LookupApi = {
  search_master(
    entityType: string,
    query: string,
    limit?: number,
  ): Promise<{ ok: boolean; error?: string; items?: LookupItem[] }>;
};

type Props = {
  entityType: "account" | "party" | "commodity";
  label: string;
  value: LookupItem | null;
  onSelect(item: LookupItem | null): void;
  required?: boolean;
  autoFocus?: boolean;
};

function Autocomplete({
  entityType,
  label,
  value,
  onSelect,
  required = false,
  autoFocus = false,
}: Props) {
  const [query, setQuery] = useState(value?.label ?? "");
  const [items, setItems] = useState<LookupItem[]>([]);
  const [open, setOpen] = useState(false);
  const [highlighted, setHighlighted] = useState(0);
  const requestId = useRef(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setQuery(value?.label ?? "");
  }, [value]);

  useEffect(() => {
    const clean = query.trim();
    if (!clean || value?.label === query) {
      setItems([]);
      setOpen(false);
      return;
    }
    const currentRequest = ++requestId.current;
    const timer = window.setTimeout(() => {
      const api = window.pywebview?.api as unknown as LookupApi | undefined;
      if (!api) return;
      void api.search_master(entityType, clean, 20).then((result) => {
        if (currentRequest !== requestId.current) return;
        const found = result.items ?? [];
        setItems(found);
        setHighlighted(0);
        setOpen(found.length > 0);
      });
    }, 90);
    return () => window.clearTimeout(timer);
  }, [entityType, query, value]);

  function focusNextControl() {
    const input = inputRef.current;
    if (!input) return;
    const container = input.closest<HTMLElement>("[data-grid-row]") ?? input.closest("form");
    const controls = container
      ? Array.from(container.querySelectorAll<HTMLElement>(
          "input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [data-grid-focus='true']:not([disabled])",
        ))
      : [];
    controls[controls.indexOf(input) + 1]?.focus();
  }

  function accept(item: LookupItem, advance = true) {
    onSelect(item);
    setQuery(item.label);
    setOpen(false);
    if (advance) window.setTimeout(focusNextControl, 0);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown" && items.length) {
      event.preventDefault();
      setOpen(true);
      setHighlighted((index) => Math.min(index + 1, items.length - 1));
    } else if (event.key === "ArrowUp" && items.length) {
      event.preventDefault();
      setHighlighted((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const exact = items.find(
        (item) => item.label.toLocaleLowerCase() === query.trim().toLocaleLowerCase(),
      );
      const selected = exact ?? items[highlighted];
      if (selected) {
        const handledByGrid = Boolean(inputRef.current?.closest("[data-grid-row]"));
        accept(selected, !handledByGrid);
      }
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <label className="lookup-field">
      {label && <span>{label}</span>}
      <input
        ref={inputRef}
        autoFocus={autoFocus}
        required={required}
        value={query}
        autoComplete="off"
        onChange={(event) => {
          setQuery(event.target.value);
          if (value) onSelect(null);
        }}
        aria-expanded={open}
        aria-haspopup="listbox"
        onFocus={() => setOpen(items.length > 0)}
        onKeyDown={handleKeyDown}
      />
      {open && (
        <ul className="lookup-list" role="listbox">
          {items.map((item, index) => (
            <li
              aria-selected={index === highlighted}
              className={index === highlighted ? "highlighted" : ""}
              key={item.id}
              onMouseDown={(event) => {
                event.preventDefault();
                accept(item);
              }}
              role="option"
            >
              {item.label}
            </li>
          ))}
        </ul>
      )}
    </label>
  );
}

export type { LookupItem };
export default Autocomplete;
