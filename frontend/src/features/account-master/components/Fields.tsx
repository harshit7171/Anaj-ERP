import { forwardRef, type ReactNode } from "react";

export function FieldLabel({
  label,
  children,
  className = "",
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={`account-master-field ${className}`.trim()}>
      <span>{label}</span>
      {children}
    </label>
  );
}

export const TextInput = forwardRef<
  HTMLInputElement,
  {
    value: string;
    onChange(value: string): void;
    enterOrder?: number;
    maxLength?: number;
    className?: string;
    disabled?: boolean;
    readOnly?: boolean;
  }
>(function TextInput(
  { value, onChange, enterOrder, maxLength, className = "", disabled, readOnly },
  ref,
) {
  return (
    <input
      ref={ref}
      className={className}
      data-enter-order={enterOrder}
      disabled={disabled}
      maxLength={maxLength}
      readOnly={readOnly}
      type="text"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  );
});

export function TextArea({
  value,
  onChange,
  enterOrder,
  rows = 2,
  className = "",
}: {
  value: string;
  onChange(value: string): void;
  enterOrder?: number;
  rows?: number;
  className?: string;
}) {
  return (
    <textarea
      className={`account-master-textarea ${className}`.trim()}
      data-enter-order={enterOrder}
      rows={rows}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}

export { default as ComboboxInput } from "../../../components/SearchableCombobox";
