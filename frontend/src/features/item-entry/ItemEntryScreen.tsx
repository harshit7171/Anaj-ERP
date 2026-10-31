import { FormEvent, useEffect, useRef, useState, type ReactNode } from "react";

import DeleteConfirmModal from "../../components/DeleteConfirmModal";
import { useFormEnterFlow } from "../../hooks/useFormEnterFlow";
import useFieldFocusHandlers from "../../hooks/useFieldFocusHandlers";
import {
  GST_UQC,
  ITEM_TYPES,
  RATE_PER_UNITS,
  SALE_SER,
  YES_NO,
  emptyItemForm,
  itemFormFromRecord,
  itemFormToPayload,
  type ItemFormState,
} from "./constants";

type ApiResult = { ok: boolean; error?: string };

type ItemApi = {
  list_items?(): Promise<ApiResult & { items?: Record<string, unknown>[] }>;
  get_item?(id: string): Promise<ApiResult & { item?: Record<string, unknown> }>;
  save_item_master?(
    payload: Record<string, unknown>,
  ): Promise<ApiResult & { item?: Record<string, unknown> }>;
  delete_item?(id: string): Promise<ApiResult>;
};

function api(): ItemApi | undefined {
  return window.pywebview?.api as unknown as ItemApi | undefined;
}

function YnSelect({
  value,
  onChange,
  disabled,
}: {
  value: string;
  onChange(value: string): void;
  disabled?: boolean;
}) {
  return (
    <select
      className="item-entry-input"
      disabled={disabled}
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
    <label className={`item-entry-field ${className ?? ""}`.trim()}>
      <span>{label}</span>
      {children}
    </label>
  );
}

export default function ItemEntryScreen({
  mode,
  onExit,
}: {
  mode: "add" | "modify";
  onExit(): void;
}) {
  const formRef = useRef<HTMLFormElement>(null);
  const title = mode === "add" ? "Master Item Add" : "Master Item Modify";

  const [form, setForm] = useState<ItemFormState>(emptyItemForm());
  const [loaded, setLoaded] = useState(mode !== "modify");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [findOpen, setFindOpen] = useState(false);
  const [findQuery, setFindQuery] = useState("");
  const [findRows, setFindRows] = useState<Record<string, unknown>[]>([]);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const fieldsLocked = mode === "modify" && !loaded;

  useFormEnterFlow(formRef, true);
  useFieldFocusHandlers(formRef, true);

  function set<K extends keyof ItemFormState>(key: K, value: ItemFormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  useEffect(() => {
    setForm(emptyItemForm());
    setLoaded(mode !== "modify");
    setError("");
    setStatus("");
    if (mode === "modify") {
      setFindOpen(true);
      void refreshFindList("");
    } else {
      void suggestNextItemCode();
    }
  }, [mode]);

  async function suggestNextItemCode() {
    const response = await api()?.list_items?.();
    if (!response?.ok || !response.items?.length) {
      set("item_code", "1");
      return;
    }
    const codes = response.items
      .map((row) => {
        let code = row.item_code;
        if (!code && row.item_metadata_json) {
          try {
            const meta = JSON.parse(String(row.item_metadata_json)) as Record<string, unknown>;
            code = meta.item_code;
          } catch {
            code = "";
          }
        }
        return Number(String(code ?? "").replace(/\D/g, ""));
      })
      .filter((n) => Number.isFinite(n) && n > 0);
    const next = codes.length ? Math.max(...codes) + 1 : 1;
    set("item_code", String(next));
  }

  async function refreshFindList(query: string) {
    const response = await api()?.list_items?.();
    if (!response?.ok) {
      setFindRows([]);
      return;
    }
    const q = query.trim().toLowerCase();
    const rows = (response.items ?? []).filter((row) => {
      if (!q) return true;
      const hay = [row.name, row.variety, row.hsn_code, row.commodity_id, row.item_code]
        .map((v) => String(v ?? "").toLowerCase())
        .join(" ");
      return hay.includes(q);
    });
    setFindRows(rows);
  }

  function applyRecord(row: Record<string, unknown>) {
    setForm(itemFormFromRecord(row));
    setLoaded(true);
    setFindOpen(false);
    setStatus("Item loaded — you can edit and save (F3).");
    setError("");
  }

  async function runFind(searchText?: string) {
    const bridge = api();
    if (!bridge) {
      setError("Desktop API is not available.");
      return;
    }
    const query = (searchText ?? form.item_code ?? findQuery).trim();
    if (mode === "modify" && query && !findOpen) {
      const detail = await bridge.get_item?.(query);
      if (detail?.ok && detail.item) {
        applyRecord(detail.item);
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
    if (!bridge?.save_item_master) {
      setError("Desktop API is not available.");
      return;
    }
    if (mode === "modify" && (!loaded || !form.commodity_id)) {
      setError("Select an item with Find (F5) before saving.");
      return;
    }
    if (!form.name.trim()) {
      setError("Item name is required.");
      return;
    }
    const response = await bridge.save_item_master(itemFormToPayload(form));
    if (!response?.ok) {
      setError(response?.error ?? "Save failed.");
      return;
    }
    setStatus("Data has been Successfully Saved");
    if (mode === "add") {
      const created = (response as ApiResult & { item?: Record<string, unknown> }).item;
      if (created?.commodity_id) {
        setForm(itemFormFromRecord(created));
      } else {
        setForm(emptyItemForm());
        void suggestNextItemCode();
      }
    }
  }

  async function confirmDelete() {
    const bridge = api();
    if (!bridge?.delete_item || !form.commodity_id) {
      setError("Nothing to delete.");
      setDeleteOpen(false);
      return;
    }
    const response = await bridge.delete_item(form.commodity_id);
    setDeleteOpen(false);
    if (!response?.ok) {
      setError(response?.error ?? "Delete failed.");
      return;
    }
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
      if (event.key === "F5" && mode === "modify") {
        event.preventDefault();
        void runFind();
      }
      if (event.key === "F6" && mode === "modify" && loaded) {
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
        className="item-entry-screen"
        data-item-entry-form
        onSubmit={(event) => void save(event)}
      >
        <h2 className="item-entry-title">{title}</h2>

        {fieldsLocked && (
          <p className="item-entry-hint" role="status">
            Use <strong>Find (F5)</strong> to select an item. Fields stay read-only until one is loaded.
          </p>
        )}

        <fieldset className="item-entry-body" disabled={fieldsLocked}>
          <div className="item-entry-row item-entry-id-row">
            <Field label="Item ID">
              <input
                className={`item-entry-input item-entry-id${mode === "add" ? " item-entry-readonly" : ""}`}
                readOnly={mode === "add"}
                value={form.item_code}
                onChange={(event) => set("item_code", event.target.value)}
              />
            </Field>
            {mode === "modify" && (
              <button className="item-entry-btn" type="button" onClick={() => void runFind()}>
                Find (F5)
              </button>
            )}
          </div>

          <Field label="Item Name" className="item-entry-span-full">
            <input
              className="item-entry-input"
              data-enter-order={1}
              value={form.name}
              onChange={(event) => set("name", event.target.value)}
            />
          </Field>

          <div className="item-entry-row-2">
            <Field label="Group">
              <input
                className="item-entry-input"
                value={form.item_group}
                onChange={(event) => set("item_group", event.target.value)}
              />
            </Field>
            <Field label="Sub-Group">
              <input
                className="item-entry-input"
                value={form.sub_group}
                onChange={(event) => set("sub_group", event.target.value)}
              />
            </Field>
          </div>

          <div className="item-entry-row-4">
            <Field label="Unit Rate Per">
              <select
                className="item-entry-input"
                value={form.rate_per}
                onChange={(event) => set("rate_per", event.target.value)}
              >
                {RATE_PER_UNITS.map((u) => (
                  <option key={u} value={u}>
                    {u}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Bardana Item">
              <YnSelect value={form.bardana_item} onChange={(v) => set("bardana_item", v)} />
            </Field>
            <Field label="Item Type">
              <select
                className="item-entry-input"
                value={form.item_type}
                onChange={(event) => set("item_type", event.target.value)}
              >
                {ITEM_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Having Yield">
              <YnSelect value={form.having_yield} onChange={(v) => set("having_yield", v)} />
            </Field>
          </div>

          <div className="item-entry-row-4">
            <Field label="Paddy">
              <YnSelect value={form.paddy} onChange={(v) => set("paddy", v)} />
            </Field>
            <Field label="Exempted">
              <YnSelect value={form.exempted} onChange={(v) => set("exempted", v)} />
            </Field>
            <Field label="Market Fee">
              <YnSelect value={form.market_fee} onChange={(v) => set("market_fee", v)} />
            </Field>
            <Field label="Market %">
              <input
                className="item-entry-input"
                value={form.market_pct}
                onChange={(event) => set("market_pct", event.target.value)}
              />
            </Field>
          </div>

          <div className="item-entry-row-4">
            <Field label="RDF Fee %">
              <input
                className="item-entry-input"
                value={form.rdf_fee_pct}
                onChange={(event) => set("rdf_fee_pct", event.target.value)}
              />
            </Field>
            <Field label="Grace Days">
              <input
                className="item-entry-input"
                value={form.grace_days}
                onChange={(event) => set("grace_days", event.target.value)}
              />
            </Field>
            <Field label="Bharti">
              <input
                className="item-entry-input"
                value={form.bharti}
                onChange={(event) => set("bharti", event.target.value)}
              />
            </Field>
            <Field label="Bardana Req.">
              <YnSelect value={form.bardana_req} onChange={(v) => set("bardana_req", v)} />
            </Field>
          </div>

          <div className="item-entry-row-3">
            <Field label="HSN Code">
              <input
                className="item-entry-input"
                value={form.hsn_code}
                onChange={(event) => set("hsn_code", event.target.value)}
              />
            </Field>
            <Field label="Stockable">
              <YnSelect value={form.stockable} onChange={(v) => set("stockable", v)} />
            </Field>
            <Field label="TDS Req.">
              <YnSelect value={form.tds_required} onChange={(v) => set("tds_required", v)} />
            </Field>
          </div>

          <div className="item-entry-row-2">
            <Field label="GST Type">
              <input
                className="item-entry-input"
                value={form.gst_type}
                onChange={(event) => set("gst_type", event.target.value)}
              />
            </Field>
            <Field label="GST Type ( H Form )">
              <input
                className="item-entry-input"
                value={form.gst_type_h_form}
                onChange={(event) => set("gst_type_h_form", event.target.value)}
              />
            </Field>
          </div>

          <Field label="UQC (GST)" className="item-entry-span-half">
            <select
              className="item-entry-input"
              value={form.uqc || "QTL"}
              onChange={(event) => set("uqc", event.target.value)}
            >
              {GST_UQC.map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </select>
          </Field>

          <div className="item-entry-section-divider" />

          <div className="item-entry-row-4">
            <Field label="Text Print For Nug">
              <input
                className="item-entry-input"
                value={form.text_print_nug}
                onChange={(event) => set("text_print_nug", event.target.value)}
              />
            </Field>
            <Field label="Text Print For Wt.">
              <input
                className="item-entry-input"
                value={form.text_print_wt}
                onChange={(event) => set("text_print_wt", event.target.value)}
              />
            </Field>
            <Field label="Sale/Ser (S/R)">
              <select
                className="item-entry-input"
                value={form.sale_ser}
                onChange={(event) => set("sale_ser", event.target.value)}
              >
                {SALE_SER.map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="K Form Req.">
              <YnSelect value={form.k_form_reg} onChange={(v) => set("k_form_reg", v)} />
            </Field>
          </div>

          <div className="item-entry-row-4">
            <Field label="RCM Pur. Require">
              <YnSelect value={form.rcm_purchase} onChange={(v) => set("rcm_purchase", v)} />
            </Field>
            <Field label="RCM Inv. Req.">
              <YnSelect value={form.rcm_inv_req} onChange={(v) => set("rcm_inv_req", v)} />
            </Field>
            <Field label="Sec 17(5) Blocked ITC">
              <YnSelect value={form.blocked_itc} onChange={(v) => set("blocked_itc", v)} />
            </Field>
            <Field label="Gross Wt/Tare Wt Req">
              <YnSelect
                value={form.gross_tare_wt_req}
                onChange={(v) => set("gross_tare_wt_req", v)}
              />
            </Field>
            <Field label="Bal. Stock Qty Msg">
              <input
                className="item-entry-input"
                value={form.bal_stock_qty_msg}
                onChange={(event) => set("bal_stock_qty_msg", event.target.value)}
              />
            </Field>
          </div>
        </fieldset>

        <div className="item-entry-actions">
          {mode === "modify" && (
            <button
              className="item-entry-btn item-entry-btn-delete"
              disabled={!loaded}
              type="button"
              onClick={() => setDeleteOpen(true)}
            >
              Delete (F6)
            </button>
          )}
          <button
            className="item-entry-btn item-entry-btn-save"
            disabled={mode === "modify" && !loaded}
            type="submit"
          >
            Save (F3)
          </button>
          <button className="item-entry-btn" type="button" onClick={onExit}>
            Cancel (F4)
          </button>
        </div>

        <footer className="item-entry-status">
          {error ? <span className="item-entry-error">{error}</span> : null}
          {!error && status ? <span className="item-entry-ok">{status}</span> : null}
        </footer>
      </form>

      {findOpen && mode === "modify" && (
        <div className="item-entry-find-overlay" role="presentation">
          <div className="item-entry-find-panel" role="dialog" aria-modal="true">
            <header>
              <strong>Find Item (F5)</strong>
              <button type="button" aria-label="Close" onClick={() => setFindOpen(false)}>
                ×
              </button>
            </header>
            <form
              className="item-entry-find-search"
              onSubmit={(event) => {
                event.preventDefault();
                void runFind(findQuery);
              }}
            >
              <input
                placeholder="ID / name / HSN"
                value={findQuery}
                onChange={(event) => {
                  setFindQuery(event.target.value);
                  void refreshFindList(event.target.value);
                }}
              />
              <button type="submit">Search</button>
            </form>
            <div className="item-entry-find-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Group</th>
                    <th>HSN</th>
                  </tr>
                </thead>
                <tbody>
                  {findRows.map((row) => (
                    <tr
                      key={String(row.commodity_id)}
                      tabIndex={0}
                      onDoubleClick={() => {
                        void api()?.get_item?.(String(row.commodity_id ?? "")).then((detail) => {
                          if (detail?.ok && detail.item) {
                            applyRecord(detail.item);
                          } else {
                            applyRecord(row);
                          }
                        });
                      }}
                    >
                      <td>{String(row.name ?? "")}</td>
                      <td>{String(row.item_group ?? "")}</td>
                      <td>{String(row.hsn_code ?? "")}</td>
                    </tr>
                  ))}
                  {!findRows.length && (
                    <tr>
                      <td colSpan={3}>No items found.</td>
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
        recordLabel={form.name || "this item"}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => void confirmDelete()}
      />
    </>
  );
}
