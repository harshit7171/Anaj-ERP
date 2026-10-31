import { FormEvent, useEffect, useRef, useState } from "react";

import DeleteConfirmModal from "../../components/DeleteConfirmModal";
import { useFormEnterFlow } from "../../hooks/useFormEnterFlow";
import useFieldFocusHandlers from "../../hooks/useFieldFocusHandlers";

type ApiResult = { ok: boolean; error?: string };

type IfscApi = {
  list_ifsc_codes?(): Promise<ApiResult & { ifsc_codes?: Record<string, unknown>[] }>;
  get_ifsc_code?(key: string): Promise<ApiResult & { ifsc?: Record<string, unknown> }>;
  save_ifsc_code?(
    payload: Record<string, unknown>,
  ): Promise<ApiResult & { ifsc?: Record<string, unknown> }>;
  delete_ifsc_code?(key: string): Promise<ApiResult>;
  list_banks?(): Promise<ApiResult & { banks?: Record<string, unknown>[] }>;
};

function api(): IfscApi | undefined {
  return window.pywebview?.api as unknown as IfscApi | undefined;
}

export default function IfscMasterScreen({
  mode,
  onExit,
}: {
  mode: "add" | "modify";
  onExit(): void;
}) {
  const formRef = useRef<HTMLFormElement>(null);
  const title = mode === "add" ? "IFSC Master Add" : "IFSC Master Modify";

  const [ifscId, setIfscId] = useState("");
  const [ifscNumber, setIfscNumber] = useState("");
  const [ifscCode, setIfscCode] = useState("");
  const [bankName, setBankName] = useState("");
  const [bankCity, setBankCity] = useState("");
  const [branchAddress, setBranchAddress] = useState("");
  const [bankSuggestions, setBankSuggestions] = useState<string[]>([]);

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

  useEffect(() => {
    setIfscId("");
    setIfscNumber("");
    setIfscCode("");
    setBankName("");
    setBankCity("");
    setBranchAddress("");
    setLoaded(mode !== "modify");
    setError("");
    setStatus("");
    if (mode === "modify") {
      setFindOpen(true);
      void refreshFindList("");
    } else {
      void suggestNextIfscNumber();
    }
  }, [mode]);

  useEffect(() => {
    void api()?.list_banks?.().then((response) => {
      if (!response?.ok || !response.banks) return;
      const names = response.banks
        .map((row) => String(row.name ?? "").trim())
        .filter(Boolean);
      setBankSuggestions([...new Set(names)].sort((a, b) => a.localeCompare(b)));
    });
  }, []);

  async function suggestNextIfscNumber() {
    const response = await api()?.list_ifsc_codes?.();
    if (!response?.ok || !response.ifsc_codes?.length) {
      setIfscNumber("1");
      return;
    }
    const codes = response.ifsc_codes
      .map((row) => Number(String(row.ifsc_number ?? "").replace(/\D/g, "")))
      .filter((n) => Number.isFinite(n) && n > 0);
    const next = codes.length ? Math.max(...codes) + 1 : 1;
    setIfscNumber(String(next));
  }

  async function refreshFindList(query: string) {
    const response = await api()?.list_ifsc_codes?.();
    if (!response?.ok) {
      setFindRows([]);
      return;
    }
    const q = query.trim().toLowerCase();
    const rows = (response.ifsc_codes ?? []).filter((row) => {
      if (!q) return true;
      const hay = [row.ifsc_number, row.ifsc_code, row.bank_name, row.city, row.ifsc_id]
        .map((v) => String(v ?? "").toLowerCase())
        .join(" ");
      return hay.includes(q);
    });
    setFindRows(rows);
  }

  function applyRecord(row: Record<string, unknown>) {
    setIfscId(String(row.ifsc_id ?? ""));
    setIfscNumber(String(row.ifsc_number ?? ""));
    setIfscCode(String(row.ifsc_code ?? ""));
    setBankName(String(row.bank_name ?? ""));
    setBankCity(String(row.city ?? ""));
    setBranchAddress(String(row.address ?? ""));
    setLoaded(true);
    setFindOpen(false);
    setStatus("IFSC record loaded — you can edit and save (F3).");
    setError("");
  }

  async function runFind(searchText?: string) {
    const bridge = api();
    if (!bridge) {
      setError("Desktop API is not available.");
      return;
    }
    const query = (searchText ?? ifscNumber ?? findQuery).trim();
    if (mode === "modify" && query && !findOpen) {
      const detail = await bridge.get_ifsc_code?.(query);
      if (detail?.ok && detail.ifsc) {
        applyRecord(detail.ifsc);
        return;
      }
    }
    await refreshFindList(query);
    setFindQuery(query);
    setFindOpen(true);
  }

  function buildPayload(): Record<string, unknown> {
    const payload: Record<string, unknown> = {
      ifsc_number: ifscNumber.trim() || null,
      ifsc_code: ifscCode.trim().toUpperCase(),
      bank_name: bankName.trim() || null,
      city: bankCity.trim() || null,
      address: branchAddress.trim() || null,
    };
    if (mode === "modify" && ifscId) {
      payload.ifsc_id = ifscId;
    }
    return payload;
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setError("");
    const bridge = api();
    if (!bridge?.save_ifsc_code) {
      setError("Desktop API is not available.");
      return;
    }
    if (mode === "modify" && (!loaded || !ifscId)) {
      setError("Select an IFSC record with Find (F5) before saving.");
      return;
    }
    if (!ifscCode.trim()) {
      setError("IFSC code is required.");
      return;
    }
    if (ifscCode.trim().length !== 11) {
      setError("IFSC code must be 11 characters.");
      return;
    }
    const response = await bridge.save_ifsc_code(buildPayload());
    if (!response?.ok) {
      setError(response?.error ?? "Save failed.");
      return;
    }
    setStatus("Data has been Successfully Saved");
    if (mode === "add") {
      setIfscCode("");
      setBankName("");
      setBankCity("");
      setBranchAddress("");
      void suggestNextIfscNumber();
    } else if (response.ifsc) {
      applyRecord(response.ifsc);
      setStatus("Data has been Successfully Saved");
    }
  }

  async function confirmDelete() {
    const bridge = api();
    const key = ifscId || ifscNumber || ifscCode;
    if (!bridge?.delete_ifsc_code || !key) {
      setError("Nothing to delete.");
      setDeleteOpen(false);
      return;
    }
    const response = await bridge.delete_ifsc_code(key);
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
        className="ifsc-master-screen"
        data-ifsc-master-form
        onSubmit={(event) => void save(event)}
      >
        <h2 className="ifsc-master-title">{title}</h2>

        {fieldsLocked && (
          <p className="ifsc-master-hint" role="status">
            Use <strong>Find (F5)</strong> to select a record. Fields stay read-only until one is
            loaded.
          </p>
        )}

        <fieldset className="ifsc-master-fields" disabled={fieldsLocked}>
          <div className="ifsc-master-row">
            <span className="ifsc-master-field-label">IFSC ID</span>
            <div className="ifsc-master-id-controls">
              <input
                className={`ifsc-master-input ifsc-master-id-input${mode === "add" ? " ifsc-master-input-readonly" : ""}`}
                readOnly={mode === "add"}
                value={ifscNumber}
                onChange={(event) => setIfscNumber(event.target.value)}
              />
              {mode === "modify" && (
                <button className="ifsc-master-btn" type="button" onClick={() => void runFind()}>
                  Find (F5)
                </button>
              )}
            </div>
          </div>

          <div className="ifsc-master-row">
            <span className="ifsc-master-field-label">IFSC Code</span>
            <input
              className="ifsc-master-input"
              data-enter-order={1}
              maxLength={11}
              value={ifscCode}
              onChange={(event) => setIfscCode(event.target.value.toUpperCase())}
            />
          </div>

          <div className="ifsc-master-row">
            <span className="ifsc-master-field-label">Bank Name</span>
            <input
              className="ifsc-master-input"
              data-enter-order={2}
              list="ifsc-master-bank-list"
              value={bankName}
              onChange={(event) => setBankName(event.target.value)}
            />
            <datalist id="ifsc-master-bank-list">
              {bankSuggestions.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
          </div>

          <div className="ifsc-master-row">
            <span className="ifsc-master-field-label">Bank City Name</span>
            <input
              className="ifsc-master-input"
              data-enter-order={3}
              value={bankCity}
              onChange={(event) => setBankCity(event.target.value)}
            />
          </div>

          <div className="ifsc-master-row ifsc-master-row-textarea">
            <span className="ifsc-master-field-label">Branch Address</span>
            <textarea
              className="ifsc-master-textarea"
              data-enter-order={4}
              rows={4}
              value={branchAddress}
              onChange={(event) => setBranchAddress(event.target.value)}
            />
          </div>
        </fieldset>

        <div className="ifsc-master-actions">
          {mode === "modify" && (
            <button
              className="ifsc-master-btn ifsc-master-btn-delete"
              disabled={!loaded}
              type="button"
              onClick={() => setDeleteOpen(true)}
            >
              Delete (F6)
            </button>
          )}
          <button
            className="ifsc-master-btn ifsc-master-btn-save"
            disabled={mode === "modify" && !loaded}
            type="submit"
          >
            Save (F3)
          </button>
          <button className="ifsc-master-btn" type="button" onClick={onExit}>
            Cancel (F4)
          </button>
        </div>

        <footer className="ifsc-master-status">
          {error ? <span className="ifsc-master-error">{error}</span> : null}
          {!error && status ? <span className="ifsc-master-ok">{status}</span> : null}
        </footer>
      </form>

      {findOpen && mode === "modify" && (
        <div className="ifsc-master-find-overlay" role="presentation">
          <div className="ifsc-master-find-panel" role="dialog" aria-modal="true">
            <header>
              <strong>Find IFSC (F5)</strong>
              <button type="button" aria-label="Close" onClick={() => setFindOpen(false)}>
                ×
              </button>
            </header>
            <form
              className="ifsc-master-find-search"
              onSubmit={(event) => {
                event.preventDefault();
                void runFind(findQuery);
              }}
            >
              <input
                placeholder="IFSC ID / code / bank"
                value={findQuery}
                onChange={(event) => {
                  setFindQuery(event.target.value);
                  void refreshFindList(event.target.value);
                }}
              />
              <button type="submit">Search</button>
            </form>
            <div className="ifsc-master-find-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>IFSC</th>
                    <th>Bank</th>
                    <th>City</th>
                  </tr>
                </thead>
                <tbody>
                  {findRows.map((row) => (
                    <tr
                      key={String(row.ifsc_id)}
                      tabIndex={0}
                      onDoubleClick={() => {
                        void api()
                          ?.get_ifsc_code?.(String(row.ifsc_id ?? ""))
                          .then((detail) => {
                            if (detail?.ok && detail.ifsc) {
                              applyRecord(detail.ifsc);
                            } else {
                              applyRecord(row);
                            }
                          });
                      }}
                    >
                      <td>{String(row.ifsc_number ?? "")}</td>
                      <td>{String(row.ifsc_code ?? "")}</td>
                      <td>{String(row.bank_name ?? "")}</td>
                      <td>{String(row.city ?? "")}</td>
                    </tr>
                  ))}
                  {!findRows.length && (
                    <tr>
                      <td colSpan={4}>No IFSC records found.</td>
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
        recordLabel={ifscCode || bankName || "this IFSC record"}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => void confirmDelete()}
      />
    </>
  );
}
