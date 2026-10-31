import { FormEvent, useEffect, useRef, useState } from "react";

import DeleteConfirmModal from "../../components/DeleteConfirmModal";
import { useFormEnterFlow } from "../../hooks/useFormEnterFlow";
import useFieldFocusHandlers from "../../hooks/useFieldFocusHandlers";

type ApiResult = { ok: boolean; error?: string };

type TransportApi = {
  list_transports?(): Promise<ApiResult & { transports?: Record<string, unknown>[] }>;
  get_transport?(id: string): Promise<ApiResult & { transport?: Record<string, unknown> }>;
  save_transport?(payload: Record<string, unknown>): Promise<ApiResult>;
  delete_transport?(id: string): Promise<ApiResult>;
};

function api(): TransportApi | undefined {
  return window.pywebview?.api as unknown as TransportApi | undefined;
}

export default function TransportMasterScreen({
  mode,
  onExit,
}: {
  mode: "add" | "modify";
  onExit(): void;
}) {
  const formRef = useRef<HTMLFormElement>(null);
  const title = mode === "add" ? "Master Transport Add" : "Master Transport Modify";

  const [transportId, setTransportId] = useState("");
  const [transportCode, setTransportCode] = useState("");
  const [transportName, setTransportName] = useState("");
  const [gstin, setGstin] = useState("");
  const [vehicleDetails, setVehicleDetails] = useState("");
  const [address, setAddress] = useState("");
  const [phone, setPhone] = useState("");
  const [contactPerson, setContactPerson] = useState("");

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
    setTransportId("");
    setTransportCode("");
    setTransportName("");
    setGstin("");
    setVehicleDetails("");
    setAddress("");
    setPhone("");
    setContactPerson("");
    setLoaded(mode !== "modify");
    setError("");
    setStatus("");
    if (mode === "modify") {
      setFindOpen(true);
      void refreshFindList("");
    } else {
      void suggestNextTransportCode();
    }
  }, [mode]);

  async function suggestNextTransportCode() {
    const response = await api()?.list_transports?.();
    if (!response?.ok || !response.transports?.length) {
      setTransportCode("1");
      return;
    }
    const codes = response.transports
      .map((row) => Number(String(row.transport_code ?? "").replace(/\D/g, "")))
      .filter((n) => Number.isFinite(n) && n > 0);
    const next = codes.length ? Math.max(...codes) + 1 : 1;
    setTransportCode(String(next));
  }

  async function refreshFindList(query: string) {
    const response = await api()?.list_transports?.();
    if (!response?.ok) {
      setFindRows([]);
      return;
    }
    const q = query.trim().toLowerCase();
    const rows = (response.transports ?? []).filter((row) => {
      if (!q) return true;
      const hay = [row.transport_code, row.name, row.gstin, row.transport_id]
        .map((v) => String(v ?? "").toLowerCase())
        .join(" ");
      return hay.includes(q);
    });
    setFindRows(rows);
  }

  function applyRecord(row: Record<string, unknown>) {
    setTransportId(String(row.transport_id ?? ""));
    setTransportCode(String(row.transport_code ?? ""));
    setTransportName(String(row.name ?? ""));
    setGstin(String(row.gstin ?? ""));
    setVehicleDetails(String(row.vehicle_details ?? ""));
    setAddress(String(row.address ?? ""));
    setPhone(String(row.phone ?? ""));
    setContactPerson(String(row.contact_person ?? ""));
    setLoaded(true);
    setFindOpen(false);
    setStatus("Transport loaded — you can edit and save (F3).");
    setError("");
  }

  async function runFind(searchText?: string) {
    const bridge = api();
    if (!bridge) {
      setError("Desktop API is not available.");
      return;
    }
    const query = (searchText ?? transportCode ?? findQuery).trim();
    if (mode === "modify" && query && !findOpen) {
      const detail = await bridge.get_transport?.(query);
      if (detail?.ok && detail.transport) {
        applyRecord(detail.transport);
        return;
      }
    }
    await refreshFindList(query);
    setFindQuery(query);
    setFindOpen(true);
  }

  function buildPayload(): Record<string, unknown> {
    const payload: Record<string, unknown> = {
      name: transportName.trim(),
      transport_code: transportCode.trim() || null,
      gstin: gstin.trim().toUpperCase() || null,
      vehicle_details: vehicleDetails.trim() || null,
      address: address.trim() || null,
      phone: phone.trim() || null,
      contact_person: contactPerson.trim() || null,
    };
    if (mode === "modify" && transportId) {
      payload.transport_id = transportId;
    }
    return payload;
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setError("");
    const bridge = api();
    if (!bridge?.save_transport) {
      setError("Desktop API is not available.");
      return;
    }
    if (mode === "modify" && (!loaded || !transportId)) {
      setError("Select a transport with Find (F5) before saving.");
      return;
    }
    if (!transportName.trim()) {
      setError("Transport name is required.");
      return;
    }
    const response = await bridge.save_transport(buildPayload());
    if (!response?.ok) {
      setError(response?.error ?? "Save failed.");
      return;
    }
    setStatus("Data has been Successfully Saved");
    if (mode === "add") {
      setTransportName("");
      setGstin("");
      setVehicleDetails("");
      setAddress("");
      setPhone("");
      setContactPerson("");
      void suggestNextTransportCode();
    }
  }

  async function confirmDelete() {
    const bridge = api();
    if (!bridge?.delete_transport || !transportId) {
      setError("Nothing to delete.");
      setDeleteOpen(false);
      return;
    }
    const response = await bridge.delete_transport(transportId);
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
        className="transport-master-screen"
        data-transport-master-form
        onSubmit={(event) => void save(event)}
      >
        <h2 className="transport-master-title">{title}</h2>

        {fieldsLocked && (
          <p className="transport-master-hint" role="status">
            Use <strong>Find (F5)</strong> to select a transport. Fields stay read-only until one is loaded.
          </p>
        )}

        <fieldset className="transport-master-fields" disabled={fieldsLocked}>
          <div className="transport-master-row transport-master-id-row">
            <span className="transport-master-field-label">Transport ID</span>
            <div className="transport-master-id-controls">
              <input
                className={`transport-master-input transport-master-id-input${mode === "add" ? " transport-master-input-readonly" : ""}`}
                data-enter-order={1}
                readOnly={mode === "add"}
                value={transportCode}
                onChange={(event) => setTransportCode(event.target.value)}
              />
              {mode === "modify" && (
                <button className="transport-master-btn" type="button" onClick={() => void runFind()}>
                  Find (F5)
                </button>
              )}
            </div>
          </div>

          <div className="transport-master-row">
            <span className="transport-master-field-label">Transport Name</span>
            <input
              className="transport-master-input"
              data-enter-order={2}
              value={transportName}
              onChange={(event) => setTransportName(event.target.value)}
            />
          </div>

          <div className="transport-master-row">
            <span className="transport-master-field-label">GST No</span>
            <input
              className="transport-master-input transport-master-gst-input"
              data-enter-order={3}
              maxLength={15}
              value={gstin}
              onChange={(event) => setGstin(event.target.value.toUpperCase())}
            />
          </div>
        </fieldset>

        <div className="transport-master-actions">
          {mode === "modify" && (
            <button
              className="transport-master-btn transport-master-btn-delete"
              disabled={!loaded}
              type="button"
              onClick={() => setDeleteOpen(true)}
            >
              Delete (F6)
            </button>
          )}
          <button
            className="transport-master-btn transport-master-btn-save"
            disabled={mode === "modify" && !loaded}
            type="submit"
          >
            Save (F3)
          </button>
          <button className="transport-master-btn" type="button" onClick={onExit}>
            Cancel (F4)
          </button>
        </div>

        <footer className="transport-master-status">
          {error ? <span className="transport-master-error">{error}</span> : null}
          {!error && status ? <span className="transport-master-ok">{status}</span> : null}
        </footer>
      </form>

      {findOpen && mode === "modify" && (
        <div className="transport-master-find-overlay" role="presentation">
          <div className="transport-master-find-panel" role="dialog" aria-modal="true">
            <header>
              <strong>Find Transport (F5)</strong>
              <button type="button" aria-label="Close" onClick={() => setFindOpen(false)}>
                ×
              </button>
            </header>
            <form
              className="transport-master-find-search"
              onSubmit={(event) => {
                event.preventDefault();
                void runFind(findQuery);
              }}
            >
              <input
                placeholder="ID / name / GST"
                value={findQuery}
                onChange={(event) => {
                  setFindQuery(event.target.value);
                  void refreshFindList(event.target.value);
                }}
              />
              <button type="submit">Search</button>
            </form>
            <div className="transport-master-find-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Transport Name</th>
                    <th>GST No</th>
                  </tr>
                </thead>
                <tbody>
                  {findRows.map((row) => (
                    <tr
                      key={String(row.transport_id)}
                      tabIndex={0}
                      onDoubleClick={() => applyRecord(row)}
                    >
                      <td>{String(row.transport_code ?? row.transport_id ?? "")}</td>
                      <td>{String(row.name ?? "")}</td>
                      <td>{String(row.gstin ?? "")}</td>
                    </tr>
                  ))}
                  {!findRows.length && (
                    <tr>
                      <td colSpan={3}>No transports found.</td>
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
        recordLabel={transportName || "this transport"}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => void confirmDelete()}
      />
    </>
  );
}
