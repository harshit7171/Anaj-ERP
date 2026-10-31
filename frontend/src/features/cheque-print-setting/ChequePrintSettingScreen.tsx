import { FormEvent, useEffect, useRef, useState, type ReactNode } from "react";

import DeleteConfirmModal from "../../components/DeleteConfirmModal";
import { useFormEnterFlow } from "../../hooks/useFormEnterFlow";
import useFieldFocusHandlers from "../../hooks/useFieldFocusHandlers";
import {
  PRINTER_MODES,
  YES_NO,
  chequePrintFormFromRecord,
  chequePrintFormToPayload,
  emptyChequePrintForm,
  type ChequePrintFormState,
} from "./constants";

type ApiResult = { ok: boolean; error?: string };

type ChequePrintApi = {
  list_cheque_print_settings?(): Promise<
    ApiResult & { cheque_print_settings?: Record<string, unknown>[] }
  >;
  get_cheque_print_setting?(key: string): Promise<
    ApiResult & { cheque_print_setting?: Record<string, unknown> }
  >;
  save_cheque_print_setting?(
    payload: Record<string, unknown>,
  ): Promise<ApiResult & { cheque_print_setting?: Record<string, unknown> }>;
  delete_cheque_print_setting?(key: string): Promise<ApiResult>;
  list_banks?(): Promise<ApiResult & { banks?: Record<string, unknown>[] }>;
};

function api(): ChequePrintApi | undefined {
  return window.pywebview?.api as unknown as ChequePrintApi | undefined;
}

function YnSelect({
  value,
  onChange,
}: {
  value: string;
  onChange(value: string): void;
}) {
  return (
    <select
      className="cheque-print-input"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    >
      {YES_NO.map((option) => (
        <option key={option} value={option}>
          {option}
        </option>
      ))}
    </select>
  );
}

function Field({
  label,
  children,
  className,
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={`cheque-print-field ${className ?? ""}`.trim()}>
      <span>{label}</span>
      {children}
    </label>
  );
}

function TextInput({
  value,
  onChange,
  enterOrder,
}: {
  value: string;
  onChange(value: string): void;
  enterOrder?: number;
}) {
  return (
    <input
      className="cheque-print-input"
      data-enter-order={enterOrder}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}

export default function ChequePrintSettingScreen({ onExit }: { onExit(): void }) {
  const formRef = useRef<HTMLFormElement>(null);
  const [form, setForm] = useState<ChequePrintFormState>(emptyChequePrintForm());
  const [bankSuggestions, setBankSuggestions] = useState<string[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [findOpen, setFindOpen] = useState(false);
  const [findQuery, setFindQuery] = useState("");
  const [findRows, setFindRows] = useState<Record<string, unknown>[]>([]);
  const [deleteOpen, setDeleteOpen] = useState(false);

  useFormEnterFlow(formRef, true);
  useFieldFocusHandlers(formRef, true);

  function set<K extends keyof ChequePrintFormState>(key: K, value: ChequePrintFormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  useEffect(() => {
    void api()?.list_banks?.().then((response) => {
      if (!response?.ok || !response.banks) return;
      const names = response.banks
        .map((row) => String(row.name ?? "").trim())
        .filter(Boolean);
      setBankSuggestions([...new Set(names)].sort((a, b) => a.localeCompare(b)));
    });
  }, []);

  async function refreshFindList(query: string) {
    const response = await api()?.list_cheque_print_settings?.();
    if (!response?.ok) {
      setFindRows([]);
      return;
    }
    const q = query.trim().toLowerCase();
    const rows = (response.cheque_print_settings ?? []).filter((row) => {
      if (!q) return true;
      const hay = [row.bank_name, row.cheque_setting_id]
        .map((v) => String(v ?? "").toLowerCase())
        .join(" ");
      return hay.includes(q);
    });
    setFindRows(rows);
  }

  function applyRecord(row: Record<string, unknown>) {
    setForm(chequePrintFormFromRecord(row));
    setFindOpen(false);
    setStatus("Cheque print setting loaded.");
    setError("");
  }

  async function runFind(searchText?: string) {
    const bridge = api();
    if (!bridge) {
      setError("Desktop API is not available.");
      return;
    }
    const query = (searchText ?? form.bank_name ?? findQuery).trim();
    if (query && !findOpen) {
      const detail = await bridge.get_cheque_print_setting?.(query);
      if (detail?.ok && detail.cheque_print_setting) {
        applyRecord(detail.cheque_print_setting);
        return;
      }
    }
    await refreshFindList(query);
    setFindQuery(query);
    setFindOpen(true);
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setError("");
    const bridge = api();
    if (!bridge?.save_cheque_print_setting) {
      setError("Desktop API is not available.");
      return;
    }
    if (!form.bank_name.trim()) {
      setError("Bank name is required.");
      return;
    }
    const response = await bridge.save_cheque_print_setting(chequePrintFormToPayload(form));
    if (!response?.ok) {
      setError(response?.error ?? "Save failed.");
      return;
    }
    if (response.cheque_print_setting) {
      setForm(chequePrintFormFromRecord(response.cheque_print_setting));
    }
    setStatus("Data has been Successfully Saved");
  }

  async function confirmDelete() {
    const bridge = api();
    const key = form.cheque_setting_id || form.bank_name;
    if (!bridge?.delete_cheque_print_setting || !key) {
      setError("Nothing to delete.");
      setDeleteOpen(false);
      return;
    }
    const response = await bridge.delete_cheque_print_setting(key);
    setDeleteOpen(false);
    if (!response?.ok) {
      setError(response?.error ?? "Delete failed.");
      return;
    }
    setForm(emptyChequePrintForm());
    onExit();
  }

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "F3") {
        event.preventDefault();
        formRef.current?.requestSubmit();
      }
      if (event.key === "F4") {
        event.preventDefault();
        onExit();
      }
      if (event.key === "F5") {
        event.preventDefault();
        void runFind();
      }
      if (event.key === "F6" && form.cheque_setting_id) {
        event.preventDefault();
        setDeleteOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <>
      <form
        ref={formRef}
        className="cheque-print-screen"
        data-cheque-print-form
        onSubmit={(event) => void save(event)}
      >
        <div className="cheque-print-header-row">
          <h2 className="cheque-print-title">Cheque Printing Setting</h2>
          <p className="cheque-print-units-note">All Figures in Centi-Meters</p>
        </div>

        <fieldset className="cheque-print-body">
          <div className="cheque-print-bank-row">
            <Field label="Bank Name" className="cheque-print-bank-field">
              <input
                className="cheque-print-input"
                data-enter-order={1}
                list="cheque-print-bank-list"
                value={form.bank_name}
                onChange={(event) => set("bank_name", event.target.value)}
              />
              <datalist id="cheque-print-bank-list">
                {bankSuggestions.map((name) => (
                  <option key={name} value={name} />
                ))}
              </datalist>
            </Field>
            <button className="cheque-print-btn" type="button" onClick={() => void runFind()}>
              Find (F5)
            </button>
          </div>

          <div className="cheque-print-row-3">
            <Field label="Width Of Chq">
              <TextInput value={form.width_of_chq} onChange={(v) => set("width_of_chq", v)} />
            </Field>
            <Field label="Height Of Chq">
              <TextInput value={form.height_of_chq} onChange={(v) => set("height_of_chq", v)} />
            </Field>
            <Field label="Printer Mode (P/L)">
              <select
                className="cheque-print-input"
                value={form.printer_mode}
                onChange={(event) => set("printer_mode", event.target.value)}
              >
                {PRINTER_MODES.map((mode) => (
                  <option key={mode} value={mode}>
                    {mode}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <div className="cheque-print-row-2">
            <Field label="Date from Top">
              <TextInput value={form.date_from_top} onChange={(v) => set("date_from_top", v)} />
            </Field>
            <Field label="From Left">
              <TextInput value={form.date_from_left} onChange={(v) => set("date_from_left", v)} />
            </Field>
          </div>

          <div className="cheque-print-row-3">
            <Field label="Name from Top">
              <TextInput value={form.name_from_top} onChange={(v) => set("name_from_top", v)} />
            </Field>
            <Field label="From Left">
              <TextInput value={form.name_from_left} onChange={(v) => set("name_from_left", v)} />
            </Field>
            <Field label="No of Character">
              <TextInput
                value={form.name_char_count}
                onChange={(v) => set("name_char_count", v)}
              />
            </Field>
          </div>

          <div className="cheque-print-row-3">
            <Field label="Amt Word Line 1 from Top">
              <TextInput
                value={form.amt_word_line1_from_top}
                onChange={(v) => set("amt_word_line1_from_top", v)}
              />
            </Field>
            <Field label="From Left">
              <TextInput
                value={form.amt_word_line1_from_left}
                onChange={(v) => set("amt_word_line1_from_left", v)}
              />
            </Field>
            <Field label="No of Character">
              <TextInput
                value={form.amt_word_line1_char_count}
                onChange={(v) => set("amt_word_line1_char_count", v)}
              />
            </Field>
          </div>

          <div className="cheque-print-row-3">
            <Field label="Amt Word Line 2 from Top">
              <TextInput
                value={form.amt_word_line2_from_top}
                onChange={(v) => set("amt_word_line2_from_top", v)}
              />
            </Field>
            <Field label="From Left">
              <TextInput
                value={form.amt_word_line2_from_left}
                onChange={(v) => set("amt_word_line2_from_left", v)}
              />
            </Field>
            <Field label="No of Character">
              <TextInput
                value={form.amt_word_line2_char_count}
                onChange={(v) => set("amt_word_line2_char_count", v)}
              />
            </Field>
          </div>

          <div className="cheque-print-row-2">
            <Field label="Amt Figure Line 1 from Top">
              <TextInput
                value={form.amt_figure_from_top}
                onChange={(v) => set("amt_figure_from_top", v)}
              />
            </Field>
            <Field label="From Left">
              <TextInput
                value={form.amt_figure_from_left}
                onChange={(v) => set("amt_figure_from_left", v)}
              />
            </Field>
          </div>

          <div className="cheque-print-row-4">
            <Field label="For Company Name Required">
              <YnSelect
                value={form.company_name_required}
                onChange={(v) => set("company_name_required", v)}
              />
            </Field>
            <Field label="For Comp Name From Top">
              <TextInput
                value={form.comp_name_from_top}
                onChange={(v) => set("comp_name_from_top", v)}
              />
            </Field>
            <Field label="From Left">
              <TextInput
                value={form.comp_name_from_left}
                onChange={(v) => set("comp_name_from_left", v)}
              />
            </Field>
            <Field label="No of Character">
              <TextInput
                value={form.comp_name_char_count}
                onChange={(v) => set("comp_name_char_count", v)}
              />
            </Field>
          </div>

          <div className="cheque-print-row-4">
            <Field label="TDS Print Required">
              <YnSelect
                value={form.tds_print_required}
                onChange={(v) => set("tds_print_required", v)}
              />
            </Field>
            <Field label="TDS Amount From Top">
              <TextInput value={form.tds_from_top} onChange={(v) => set("tds_from_top", v)} />
            </Field>
            <Field label="From Left">
              <TextInput value={form.tds_from_left} onChange={(v) => set("tds_from_left", v)} />
            </Field>
            <Field label="No of Character">
              <TextInput value={form.tds_char_count} onChange={(v) => set("tds_char_count", v)} />
            </Field>
          </div>

          <div className="cheque-print-sign-block">
            <div className="cheque-print-row-4">
              <Field label="Signature (1) Required">
                <YnSelect value={form.sign1_required} onChange={(v) => set("sign1_required", v)} />
              </Field>
              <Field label="Print In Sign1" className="cheque-print-span-3">
                <TextInput
                  value={form.print_in_sign1}
                  onChange={(v) => set("print_in_sign1", v)}
                />
              </Field>
            </div>
            <div className="cheque-print-row-2">
              <Field label="Signature (1) from Top">
                <TextInput value={form.sign1_from_top} onChange={(v) => set("sign1_from_top", v)} />
              </Field>
              <Field label="From Left">
                <TextInput
                  value={form.sign1_from_left}
                  onChange={(v) => set("sign1_from_left", v)}
                />
              </Field>
            </div>
          </div>

          <div className="cheque-print-sign-block">
            <div className="cheque-print-row-4">
              <Field label="Signature (2) Required">
                <YnSelect value={form.sign2_required} onChange={(v) => set("sign2_required", v)} />
              </Field>
              <Field label="Print In Sign2" className="cheque-print-span-3">
                <TextInput
                  value={form.print_in_sign2}
                  onChange={(v) => set("print_in_sign2", v)}
                />
              </Field>
            </div>
            <div className="cheque-print-row-2">
              <Field label="Signature (2) from Top">
                <TextInput value={form.sign2_from_top} onChange={(v) => set("sign2_from_top", v)} />
              </Field>
              <Field label="From Left">
                <TextInput
                  value={form.sign2_from_left}
                  onChange={(v) => set("sign2_from_left", v)}
                />
              </Field>
            </div>
          </div>

          <div className="cheque-print-sign-block">
            <div className="cheque-print-row-4">
              <Field label="Signature (3) Required">
                <YnSelect value={form.sign3_required} onChange={(v) => set("sign3_required", v)} />
              </Field>
              <Field label="Print In Sign3" className="cheque-print-span-3">
                <TextInput
                  value={form.print_in_sign3}
                  onChange={(v) => set("print_in_sign3", v)}
                />
              </Field>
            </div>
            <div className="cheque-print-row-2">
              <Field label="Signature (3) from Top">
                <TextInput value={form.sign3_from_top} onChange={(v) => set("sign3_from_top", v)} />
              </Field>
              <Field label="From Left">
                <TextInput
                  value={form.sign3_from_left}
                  onChange={(v) => set("sign3_from_left", v)}
                />
              </Field>
            </div>
          </div>

          <div className="cheque-print-row-3">
            <Field label="Date Font">
              <TextInput value={form.date_font} onChange={(v) => set("date_font", v)} />
            </Field>
            <Field label="Font Name">
              <TextInput value={form.name_font} onChange={(v) => set("name_font", v)} />
            </Field>
            <Field label="Amt Word Line1 Font">
              <TextInput
                value={form.amt_word_line1_font}
                onChange={(v) => set("amt_word_line1_font", v)}
              />
            </Field>
          </div>

          <div className="cheque-print-row-3">
            <Field label="Amt Figure Font">
              <TextInput
                value={form.amt_figure_font}
                onChange={(v) => set("amt_figure_font", v)}
              />
            </Field>
            <Field label="Tds Figure Font">
              <TextInput
                value={form.tds_figure_font}
                onChange={(v) => set("tds_figure_font", v)}
              />
            </Field>
            <Field label="Amt Word Line2 Font">
              <TextInput
                value={form.amt_word_line2_font}
                onChange={(v) => set("amt_word_line2_font", v)}
              />
            </Field>
          </div>

          <div className="cheque-print-row-1">
            <Field label="Show * (Star)">
              <YnSelect value={form.show_star} onChange={(v) => set("show_star", v)} />
            </Field>
          </div>
        </fieldset>

        <div className="cheque-print-actions">
          <button
            className="cheque-print-btn cheque-print-btn-delete"
            disabled={!form.cheque_setting_id}
            type="button"
            onClick={() => setDeleteOpen(true)}
          >
            Delete (F6)
          </button>
          <button className="cheque-print-btn cheque-print-btn-save" type="submit">
            Save (F3)
          </button>
          <button className="cheque-print-btn" type="button" onClick={onExit}>
            Cancel (F4)
          </button>
        </div>

        <footer className="cheque-print-status">
          {error ? <span className="cheque-print-error">{error}</span> : null}
          {!error && status ? <span className="cheque-print-ok">{status}</span> : null}
        </footer>
      </form>

      {findOpen && (
        <div className="cheque-print-find-overlay" role="presentation">
          <div className="cheque-print-find-panel" role="dialog" aria-modal="true">
            <header>
              <strong>Find bank setting (F5)</strong>
              <button type="button" aria-label="Close" onClick={() => setFindOpen(false)}>
                ×
              </button>
            </header>
            <form
              className="cheque-print-find-search"
              onSubmit={(event) => {
                event.preventDefault();
                void runFind(findQuery);
              }}
            >
              <input
                placeholder="Bank name"
                value={findQuery}
                onChange={(event) => {
                  setFindQuery(event.target.value);
                  void refreshFindList(event.target.value);
                }}
              />
              <button type="submit">Search</button>
            </form>
            <div className="cheque-print-find-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Bank Name</th>
                  </tr>
                </thead>
                <tbody>
                  {findRows.map((row) => (
                    <tr
                      key={String(row.cheque_setting_id)}
                      tabIndex={0}
                      onDoubleClick={() => {
                        void api()
                          ?.get_cheque_print_setting?.(String(row.cheque_setting_id ?? ""))
                          .then((detail) => {
                            if (detail?.ok && detail.cheque_print_setting) {
                              applyRecord(detail.cheque_print_setting);
                            } else {
                              applyRecord(row);
                            }
                          });
                      }}
                    >
                      <td>{String(row.bank_name ?? "")}</td>
                    </tr>
                  ))}
                  {!findRows.length && (
                    <tr>
                      <td colSpan={1}>No settings found.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      <DeleteConfirmModal
        open={deleteOpen}
        recordLabel={form.bank_name || "this cheque setting"}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => void confirmDelete()}
      />
    </>
  );
}
