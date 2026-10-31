import { FormEvent, useEffect, useRef, useState } from "react";

import DeleteConfirmModal from "../../components/DeleteConfirmModal";
import { useFormEnterFlow } from "../../hooks/useFormEnterFlow";
import useFieldFocusHandlers from "../../hooks/useFieldFocusHandlers";

type ApiResult = { ok: boolean; error?: string };

type NarrationApi = {
  list_narrations?(): Promise<ApiResult & { narrations?: Record<string, unknown>[] }>;
  get_narration?(id: string): Promise<ApiResult & { narration?: Record<string, unknown> }>;
  save_narration?(payload: Record<string, unknown>): Promise<ApiResult>;
  delete_narration?(id: string): Promise<ApiResult>;
};

function api(): NarrationApi | undefined {
  return window.pywebview?.api as unknown as NarrationApi | undefined;
}

export default function NarrationMasterScreen({
  mode,
  onExit,
}: {
  mode: "add" | "modify";
  onExit(): void;
}) {
  const formRef = useRef<HTMLFormElement>(null);
  const title = mode === "add" ? "Voucher Narration Master Add" : "Voucher Narration Master Modify";

  const [narrationId, setNarrationId] = useState("");
  const [shortCode, setShortCode] = useState("");
  const [particulars, setParticulars] = useState("");
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
    setNarrationId("");
    setShortCode("");
    setParticulars("");
    setLoaded(mode !== "modify");
    setError("");
    setStatus("");
    if (mode === "modify") {
      setFindOpen(true);
      void refreshFindList("");
    } else {
      void suggestNextShortCode();
    }
  }, [mode]);

  async function suggestNextShortCode() {
    const response = await api()?.list_narrations?.();
    if (!response?.ok || !response.narrations?.length) {
      setShortCode("1");
      return;
    }
    const codes = response.narrations
      .map((row) => Number(String(row.short_code ?? "").replace(/\D/g, "")))
      .filter((n) => Number.isFinite(n) && n > 0);
    const next = codes.length ? Math.max(...codes) + 1 : 1;
    setShortCode(String(next));
  }

  async function refreshFindList(query: string) {
    const response = await api()?.list_narrations?.();
    if (!response?.ok) {
      setFindRows([]);
      return;
    }
    const q = query.trim().toLowerCase();
    const rows = (response.narrations ?? []).filter((row) => {
      if (!q) return true;
      const hay = [
        row.short_code,
        row.narration_text,
        row.narration_id,
      ]
        .map((v) => String(v ?? "").toLowerCase())
        .join(" ");
      return hay.includes(q);
    });
    setFindRows(rows);
  }

  function applyRecord(row: Record<string, unknown>) {
    setNarrationId(String(row.narration_id ?? ""));
    setShortCode(String(row.short_code ?? ""));
    setParticulars(String(row.narration_text ?? ""));
    setLoaded(true);
    setFindOpen(false);
    setStatus("Narration loaded — you can edit and save (F3).");
    setError("");
  }

  async function runFind(searchText?: string) {
    const bridge = api();
    if (!bridge) {
      setError("Desktop API is not available.");
      return;
    }
    const query = (searchText ?? shortCode ?? findQuery).trim();
    if (mode === "modify" && query && !findOpen) {
      const detail = await bridge.get_narration?.(query);
      if (detail?.ok && detail.narration) {
        applyRecord(detail.narration);
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
    if (!bridge?.save_narration) {
      setError("Desktop API is not available.");
      return;
    }
    if (mode === "modify" && (!loaded || !narrationId)) {
      setError("Select a narration with Find (F5) before saving.");
      return;
    }
    if (!particulars.trim()) {
      setError("Particulars are required.");
      return;
    }
    const payload: Record<string, unknown> = {
      narration_text: particulars.trim(),
      short_code: shortCode.trim() || null,
    };
    if (mode === "modify" && narrationId) {
      payload.narration_id = narrationId;
    }
    const response = await bridge.save_narration(payload);
    if (!response?.ok) {
      setError(response?.error ?? "Save failed.");
      return;
    }
    setStatus("Data has been Successfully Saved");
    if (mode === "add") {
      setParticulars("");
      void suggestNextShortCode();
    }
  }

  async function confirmDelete() {
    const bridge = api();
    if (!bridge?.delete_narration || !narrationId) {
      setError("Nothing to delete.");
      setDeleteOpen(false);
      return;
    }
    const response = await bridge.delete_narration(narrationId);
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
        className="narration-master-screen"
        data-voucher-narration-form
        onSubmit={(event) => void save(event)}
      >
        <h2 className="narration-master-title">{title}</h2>

        {fieldsLocked && (
          <p className="narration-master-hint" role="status">
            Use <strong>Find (F5)</strong> to select a narration. Fields stay read-only until one is loaded.
          </p>
        )}

        <fieldset className="narration-master-fields" disabled={fieldsLocked}>
          <div className="narration-master-row narration-id-row">
            <label className="narration-master-label">
              Narration ID
              <input
                className="narration-master-input narration-id-input"
                data-enter-order={1}
                value={shortCode}
                onChange={(event) => setShortCode(event.target.value)}
              />
            </label>
            {mode === "modify" && (
              <button className="narration-master-btn" type="button" onClick={() => void runFind()}>
                Find (F5)
              </button>
            )}
          </div>

          <label className="narration-master-label">
            Particulars
            <textarea
              className="narration-master-textarea"
              data-enter-order={2}
              rows={8}
              value={particulars}
              onChange={(event) => setParticulars(event.target.value)}
            />
          </label>
        </fieldset>

        <div className="narration-master-actions">
          {mode === "modify" && (
            <button
              className="narration-master-btn narration-master-btn-delete"
              disabled={!loaded}
              type="button"
              onClick={() => setDeleteOpen(true)}
            >
              Delete (F6)
            </button>
          )}
          <button
            className="narration-master-btn narration-master-btn-save"
            disabled={mode === "modify" && !loaded}
            type="submit"
          >
            Save (F3)
          </button>
          <button className="narration-master-btn" type="button" onClick={onExit}>
            Cancel (F4)
          </button>
        </div>

        <footer className="narration-master-status">
          {error ? <span className="narration-master-error">{error}</span> : null}
          {!error && status ? <span className="narration-master-ok">{status}</span> : null}
        </footer>
      </form>

      {findOpen && mode === "modify" && (
        <div className="narration-master-find-overlay" role="presentation">
          <div className="narration-master-find-panel" role="dialog" aria-modal="true">
            <header>
              <strong>Find Narration (F5)</strong>
              <button type="button" aria-label="Close" onClick={() => setFindOpen(false)}>
                ×
              </button>
            </header>
            <form
              className="narration-master-find-search"
              onSubmit={(event) => {
                event.preventDefault();
                void runFind(findQuery);
              }}
            >
              <input
                placeholder="ID / code / text"
                value={findQuery}
                onChange={(event) => {
                  setFindQuery(event.target.value);
                  void refreshFindList(event.target.value);
                }}
              />
              <button type="submit">Search</button>
            </form>
            <div className="narration-master-find-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Particulars</th>
                  </tr>
                </thead>
                <tbody>
                  {findRows.map((row) => (
                    <tr
                      key={String(row.narration_id)}
                      tabIndex={0}
                      onDoubleClick={() => applyRecord(row)}
                    >
                      <td>{String(row.short_code ?? row.narration_id ?? "")}</td>
                      <td>{String(row.narration_text ?? "")}</td>
                    </tr>
                  ))}
                  {!findRows.length && (
                    <tr>
                      <td colSpan={2}>No narrations found.</td>
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
        recordLabel={particulars.slice(0, 40) || "this narration"}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => void confirmDelete()}
      />
    </>
  );
}
