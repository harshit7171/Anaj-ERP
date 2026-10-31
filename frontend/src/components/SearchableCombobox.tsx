import { KeyboardEvent, useEffect, useId, useMemo, useRef, useState } from "react";

type SearchableComboboxProps = {
  value: string;
  options: readonly string[];
  onChange(value: string): void;
  disabled?: boolean;
  enterOrder?: number;
  className?: string;
  placeholder?: string;
  "aria-label"?: string;
};

function SearchableCombobox({
  value,
  options,
  onChange,
  disabled = false,
  enterOrder,
  className = "",
  placeholder = "Select…",
  "aria-label": ariaLabel,
}: SearchableComboboxProps) {
  const listId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState(value);
  const [highlighted, setHighlighted] = useState(0);

  useEffect(() => {
    setQuery(value);
  }, [value]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [...options];
    return options.filter((opt) => opt.toLowerCase().includes(q));
  }, [options, query]);

  useEffect(() => {
    setHighlighted(0);
  }, [filtered.length, open]);

  function select(option: string) {
    onChange(option);
    setQuery(option);
    setOpen(false);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (disabled) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setHighlighted((i) => Math.min(i + 1, Math.max(filtered.length - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      setHighlighted((i) => Math.max(i - 1, 0));
    } else if (event.key === "Enter" && open && filtered.length) {
      event.preventDefault();
      select(filtered[highlighted] ?? filtered[0]);
    } else if (event.key === "Escape") {
      setOpen(false);
      setQuery(value);
    }
  }

  return (
    <div className={`searchable-combobox ${className}`.trim()}>
      <input
        ref={inputRef}
        aria-autocomplete="list"
        aria-controls={listId}
        aria-expanded={open}
        aria-label={ariaLabel}
        autoComplete="off"
        className="searchable-combobox-input"
        data-enter-order={enterOrder}
        disabled={disabled}
        placeholder={placeholder}
        role="combobox"
        type="text"
        value={query}
        onBlur={() => window.setTimeout(() => setOpen(false), 120)}
        onChange={(event) => {
          setQuery(event.target.value);
          setOpen(true);
          const exact = options.find(
            (opt) => opt.toLowerCase() === event.target.value.trim().toLowerCase(),
          );
          if (exact) onChange(exact);
        }}
        onFocus={() => !disabled && setOpen(true)}
        onKeyDown={handleKeyDown}
      />
      <button
        aria-label="Toggle options"
        className="searchable-combobox-chevron"
        disabled={disabled}
        tabIndex={-1}
        type="button"
        onMouseDown={(event) => {
          event.preventDefault();
          if (disabled) return;
          setOpen((current) => !current);
          inputRef.current?.focus();
        }}
      >
        ▾
      </button>
      {open && !disabled && filtered.length > 0 && (
        <ul className="searchable-combobox-list" id={listId} role="listbox">
          {filtered.map((option, index) => (
            <li
              key={option}
              aria-selected={index === highlighted}
              className={index === highlighted ? "highlighted" : ""}
              role="option"
              onMouseDown={(event) => {
                event.preventDefault();
                select(option);
              }}
            >
              {option}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default SearchableCombobox;
