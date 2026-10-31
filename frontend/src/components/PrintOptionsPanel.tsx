import { useState } from "react";

export type PrintColumnToggles = {
  moisture: boolean;
  tare: boolean;
};

export type PrintOptions = {
  copies: number;
  use_escpos: boolean;
  escpos_columns: 80 | 132;
  visible_columns: PrintColumnToggles;
  auto_print_on_save: boolean;
};

const defaults: PrintOptions = {
  copies: 3,
  use_escpos: true,
  escpos_columns: 80,
  visible_columns: { moisture: true, tare: true },
  auto_print_on_save: false,
};

function PrintOptionsPanel({
  value,
  onChange,
}: {
  value?: PrintOptions;
  onChange(next: PrintOptions): void;
}) {
  const current = value ?? defaults;
  const [local, setLocal] = useState(current);

  function update(patch: Partial<PrintOptions>) {
    const next = { ...local, ...patch };
    setLocal(next);
    onChange(next);
  }

  return (
    <fieldset className="print-options-panel text-xs">
      <legend>Print / export options</legend>
      <label>
        Copies on save
        <select
          value={local.copies}
          onChange={(e) => update({ copies: Number(e.target.value) })}
        >
          <option value={1}>1 — Original only</option>
          <option value={2}>2 — Original + Mandi duplicate</option>
          <option value={3}>3 — Farmer, Mandi Board, Arhtiya</option>
        </select>
      </label>
      <label className="checkbox-label">
        <input
          checked={local.use_escpos}
          type="checkbox"
          onChange={(e) => update({ use_escpos: e.target.checked })}
        />
        ESC/POS dot-matrix (raw, no Windows GDI spool)
      </label>
      <label>
        Dot-matrix width
        <select
          value={local.escpos_columns}
          onChange={(e) => update({ escpos_columns: Number(e.target.value) as 80 | 132 })}
        >
          <option value={80}>80 column (42 chars)</option>
          <option value={132}>132 column (72 chars)</option>
        </select>
      </label>
      <label className="checkbox-label">
        <input
          checked={local.visible_columns.moisture}
          type="checkbox"
          onChange={(e) =>
            update({
              visible_columns: { ...local.visible_columns, moisture: e.target.checked },
            })
          }
        />
        Show moisture on print
      </label>
      <label className="checkbox-label">
        <input
          checked={local.auto_print_on_save}
          type="checkbox"
          onChange={(e) => update({ auto_print_on_save: e.target.checked })}
        />
        Auto-print copies when voucher saves
      </label>
      <label className="checkbox-label">
        <input
          checked={local.visible_columns.tare}
          type="checkbox"
          onChange={(e) =>
            update({
              visible_columns: { ...local.visible_columns, tare: e.target.checked },
            })
          }
        />
        Show tare / bardana on print
      </label>
    </fieldset>
  );
}

export default PrintOptionsPanel;
export { defaults as defaultPrintOptions };
