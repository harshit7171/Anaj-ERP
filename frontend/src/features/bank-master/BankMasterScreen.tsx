import { FormEvent, useEffect, useRef, useState } from "react";

import { useFormEnterFlow } from "../../hooks/useFormEnterFlow";
import useFieldFocusHandlers from "../../hooks/useFieldFocusHandlers";

type ApiResult = { ok: boolean; error?: string };

type BankApi = {
  list_banks?(): Promise<ApiResult & { banks?: Record<string, unknown>[] }>;
  get_bank?(key: string): Promise<ApiResult & { bank?: Record<string, unknown> }>;
  save_bank?(
    payload: Record<string, unknown>,
  ): Promise<ApiResult & { bank?: Record<string, unknown> }>;
};

function api(): BankApi | undefined {
  return window.pywebview?.api as unknown as BankApi | undefined;
}

export default function BankMasterScreen({
  mode,
  onExit,
}: {
  mode: "add" | "modify";
  onExit(): void;
}) {
  const formRef = useRef<HTMLFormElement>(null);
  const title = mode === "add" ? "Bank Master Add" : "Bank Master Modify";

  const [bankId, setBankId] = useState("");
  const [bankCode, setBankCode] = useState("");
  const [bankName, setBankName] = useState("");

  const [loaded, setLoaded] = useState(mode !== "modify");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [findOpen, setFindOpen] = useState(false);
  const [findQuery, setFindQuery] = useState("");
  const [findRows, setFindRows] = useState<Record<string, unknown>[]>([]);

  const fieldsLocked = mode === "modify" && !loaded;

  useFormEnterFlow(formRef, true);
  useFieldFocusHandlers(formRef, true);

  useEffect(() => {
    setBankId("");
    setBankCode("");
    setBankName("");
    setLoaded(mode !== "modify");
    setError("");
    setStatus("");
    if (mode === "modify") {
      setFindOpen(true);
      void refreshFindList("");
    } else {
      void suggestNextBankCode();
    }
  }, [mode]);

  async function suggestNextBankCode() {
    const response = await api()?.list_banks?.();
    if (!response?.ok || !response.banks?.length) {
      setBankCode("1");
      return;
    }
    const codes = response.banks
      .map((row) => Number(String(row.bank_code ?? "").replace(/\D/g, "")))
      .filter((n) => Number.isFinite(n) && n > 0);
    const next = codes.length ? Math.max(...codes) + 1 : 1;
    setBankCode(String(next));
  }

  async function refreshFindList(query: string) {
    const response = await api()?.list_banks?.();
    if (!response?.ok) {
      setFindRows([]);
      return;
    }
    const q = query.trim().toLowerCase();
    const rows = (response.banks ?? []).filter((row) => {
      if (!q) return true;
      const hay = [row.bank_code, row.name, row.bank_id]
        .map((v) => String(v ?? "").toLowerCase())
        .join(" ");
      return hay.includes(q);
    });
    setFindRows(rows);
  }

  function applyRecord(row: Record<string, unknown>) {
    setBankId(String(row.bank_id ?? ""));
    setBankCode(String(row.bank_code ?? ""));
    setBankName(String(row.name ?? ""));
    setLoaded(true);
    setFindOpen(false);
    setStatus("Bank loaded — you can edit and save (F3).");
    setError("");
  }

  async function runFind(searchText?: string) {
    const bridge = api();
    if (!bridge) {
      setError("Desktop API is not available.");
      return;
    }
    const query = (searchText ?? bankCode ?? findQuery).trim();
    if (mode === "modify" && query && !findOpen) {
      const detail = await bridge.get_bank?.(query);
      if (detail?.ok && detail.bank) {
        applyRecord(detail.bank);
        return;
      }
    }
    await refreshFindList(query);
    setFindQuery(query);
    setFindOpen(true);
  }

  function buildPayload(): Record<string, unknown> {
    const payload: Record<string, unknown> = {
      name: bankName.trim(),
      bank_code: bankCode.trim() || null,
    };
    if (mode === "modify" && bankId) {
      payload.bank_id = bankId;
    }
    return payload;
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setError("");
    const bridge = api();
    if (!bridge?.save_bank) {
      setError("Desktop API is not available.");
      return;
    }
    if (mode === "modify" && (!loaded || !bankId)) {
      setError("Select a bank with Find (F5) before saving.");
      return;
    }
    if (!bankName.trim()) {
      setError("Bank name is required.");
      return;
    }
    const response = await bridge.save_bank(buildPayload());
    if (!response?.ok) {
      setError(response?.error ?? "Save failed.");
      return;
    }
    setStatus("Data has been Successfully Saved");
    if (mode === "add") {
      setBankName("");
      void suggestNextBankCode();
    } else if (response.bank) {
      applyRecord(response.bank);
      setStatus("Data has been Successfully Saved");
    }
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
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <>
      <form
        ref={formRef}
        className="bank-master-screen"
        data-bank-master-form
        onSubmit={(event) => void save(event)}
      >
        <h2 className="bank-master-title">{title}</h2>

        {fieldsLocked && (
          <p className="bank-master-hint" role="status">
            Use <strong>Find (F5)</strong> to select a bank. Fields stay read-only until one is loaded.
          </p>
        )}

        <fieldset className="bank-master-fields" disabled={fieldsLocked}>
          <div className="bank-master-row">
            <span className="bank-master-field-label">Bank ID</span>
            <div className="bank-master-id-controls">
              <input
                className={`bank-master-input bank-master-id-input${mode === "add" ? " bank-master-input-readonly" : ""}`}
                data-enter-order={1}
                readOnly={mode === "add"}
                value={bankCode}
                onChange={(event) => setBankCode(event.target.value)}
              />
              {mode === "modify" && (
                <button className="bank-master-btn" type="button" onClick={() => void runFind()}>
                  Find (F5)
                </button>
              )}
            </div>
          </div>

          <div className="bank-master-row">
            <span className="bank-master-field-label">Bank Name</span>
            <input
              className="bank-master-input"
              data-enter-order={2}
              value={bankName}
              onChange={(event) => setBankName(event.target.value)}
            />
          </div>
        </fieldset>

        <div className="bank-master-actions">
          <button
            className="bank-master-btn bank-master-btn-save"
            disabled={mode === "modify" && !loaded}
            type="submit"
          >
            Save (F3)
          </button>
          <button className="bank-master-btn" type="button" onClick={onExit}>
            Cancel (F4)
          </button>
        </div>

        <footer className="bank-master-status">
          {error ? <span className="bank-master-error">{error}</span> : null}
          {!error && status ? <span className="bank-master-ok">{status}</span> : null}
        </footer>
      </form>

      {findOpen && mode === "modify" && (
        <div className="bank-master-find-overlay" role="presentation">
          <div className="bank-master-find-panel" role="dialog" aria-modal="true">
            <header>
              <strong>Find Bank (F5)</strong>
              <button type="button" aria-label="Close" onClick={() => setFindOpen(false)}>
                ×
              </button>
            </header>
            <form
              className="bank-master-find-search"
              onSubmit={(event) => {
                event.preventDefault();
                void runFind(findQuery);
              }}
            >
              <input
                placeholder="Bank ID / name"
                value={findQuery}
                onChange={(event) => {
                  setFindQuery(event.target.value);
                  void refreshFindList(event.target.value);
                }}
              />
              <button type="submit">Search</button>
            </form>
            <div className="bank-master-find-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Bank Name</th>
                  </tr>
                </thead>
                <tbody>
                  {findRows.map((row) => (
                    <tr
                      key={String(row.bank_id)}
                      tabIndex={0}
                      onDoubleClick={() => {
                        void api()?.get_bank?.(String(row.bank_id ?? "")).then((detail) => {
                          if (detail?.ok && detail.bank) {
                            applyRecord(detail.bank);
                          } else {
                            applyRecord(row);
                          }
                        });
                      }}
                    >
                      <td>{String(row.bank_code ?? "")}</td>
                      <td>{String(row.name ?? "")}</td>
                    </tr>
                  ))}
                  {!findRows.length && (
                    <tr>
                      <td colSpan={2}>No banks found.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
