import { FormEvent, useEffect, useRef, useState } from "react";

import DeleteConfirmModal from "../../components/DeleteConfirmModal";
import { useFormEnterFlow } from "../../hooks/useFormEnterFlow";
import useFieldFocusHandlers from "../../hooks/useFieldFocusHandlers";

type ApiResult = { ok: boolean; error?: string };

type CityApi = {
  list_cities?(): Promise<ApiResult & { cities?: Record<string, unknown>[] }>;
  get_city?(id: string): Promise<ApiResult & { city?: Record<string, unknown> }>;
  save_city?(payload: Record<string, unknown>): Promise<ApiResult>;
  delete_city?(id: string): Promise<ApiResult>;
};

function api(): CityApi | undefined {
  return window.pywebview?.api as unknown as CityApi | undefined;
}

const FOCAL_OPTIONS = ["Y", "N"] as const;

export default function CityMasterScreen({
  mode,
  onExit,
}: {
  mode: "add" | "modify";
  onExit(): void;
}) {
  const formRef = useRef<HTMLFormElement>(null);
  const title = mode === "add" ? "City Master Add" : "City Master Modify";

  const [cityId, setCityId] = useState("");
  const [cityCode, setCityCode] = useState("");
  const [cityName, setCityName] = useState("");
  const [district, setDistrict] = useState("");
  const [stateName, setStateName] = useState("");
  const [stateCode, setStateCode] = useState("");
  const [country, setCountry] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");
  const [focalPoint, setFocalPoint] = useState<(typeof FOCAL_OPTIONS)[number]>("N");

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
    setCityId("");
    setCityCode("");
    setCityName("");
    setDistrict("");
    setStateName("");
    setStateCode("");
    setCountry("");
    setJurisdiction("");
    setFocalPoint("N");
    setLoaded(mode !== "modify");
    setError("");
    setStatus("");
    if (mode === "modify") {
      setFindOpen(true);
      void refreshFindList("");
    } else {
      void suggestNextCityCode();
    }
  }, [mode]);

  async function suggestNextCityCode() {
    const response = await api()?.list_cities?.();
    if (!response?.ok || !response.cities?.length) {
      setCityCode("1");
      return;
    }
    const codes = response.cities
      .map((row) => Number(String(row.city_code ?? "").replace(/\D/g, "")))
      .filter((n) => Number.isFinite(n) && n > 0);
    const next = codes.length ? Math.max(...codes) + 1 : 1;
    setCityCode(String(next));
  }

  async function refreshFindList(query: string) {
    const response = await api()?.list_cities?.();
    if (!response?.ok) {
      setFindRows([]);
      return;
    }
    const q = query.trim().toLowerCase();
    const rows = (response.cities ?? []).filter((row) => {
      if (!q) return true;
      const hay = [
        row.city_code,
        row.name,
        row.district_name,
        row.state_name,
        row.city_id,
      ]
        .map((v) => String(v ?? "").toLowerCase())
        .join(" ");
      return hay.includes(q);
    });
    setFindRows(rows);
  }

  function applyRecord(row: Record<string, unknown>) {
    setCityId(String(row.city_id ?? ""));
    setCityCode(String(row.city_code ?? ""));
    setCityName(String(row.name ?? ""));
    setDistrict(String(row.district_name ?? ""));
    setStateName(String(row.state_name ?? ""));
    setStateCode(String(row.state_code ?? ""));
    setCountry(String(row.country ?? ""));
    setJurisdiction(String(row.jurisdiction ?? ""));
    const fp = String(row.focal_point ?? "N").toUpperCase();
    setFocalPoint(fp === "Y" ? "Y" : "N");
    setLoaded(true);
    setFindOpen(false);
    setStatus("City loaded — you can edit and save (F3).");
    setError("");
  }

  async function runFind(searchText?: string) {
    const bridge = api();
    if (!bridge) {
      setError("Desktop API is not available.");
      return;
    }
    const query = (searchText ?? cityCode ?? findQuery).trim();
    if (mode === "modify" && query && !findOpen) {
      const detail = await bridge.get_city?.(query);
      if (detail?.ok && detail.city) {
        applyRecord(detail.city);
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
    if (!bridge?.save_city) {
      setError("Desktop API is not available.");
      return;
    }
    if (mode === "modify" && (!loaded || !cityId)) {
      setError("Select a city with Find (F5) before saving.");
      return;
    }
    if (!cityName.trim()) {
      setError("City is required.");
      return;
    }
    const payload: Record<string, unknown> = {
      name: cityName.trim(),
      city_code: cityCode.trim() || null,
      district_name: district.trim() || null,
      state_name: stateName.trim() || null,
      state_code: stateCode.trim() || null,
      country: country.trim() || null,
      jurisdiction: jurisdiction.trim() || null,
      focal_point: focalPoint,
    };
    if (mode === "modify" && cityId) {
      payload.city_id = cityId;
    }
    const response = await bridge.save_city(payload);
    if (!response?.ok) {
      setError(response?.error ?? "Save failed.");
      return;
    }
    setStatus("Data has been Successfully Saved");
    if (mode === "add") {
      setCityName("");
      setDistrict("");
      setStateName("");
      setStateCode("");
      setCountry("");
      setJurisdiction("");
      setFocalPoint("N");
      void suggestNextCityCode();
    }
  }

  async function confirmDelete() {
    const bridge = api();
    if (!bridge?.delete_city || !cityId) {
      setError("Nothing to delete.");
      setDeleteOpen(false);
      return;
    }
    const response = await bridge.delete_city(cityId);
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
        className="city-master-screen"
        data-city-master-form
        onSubmit={(event) => void save(event)}
      >
        <h2 className="city-master-title">{title}</h2>

        {fieldsLocked && (
          <p className="city-master-hint" role="status">
            Use <strong>Find (F5)</strong> to select a city. Fields stay read-only until one is loaded.
          </p>
        )}

        <fieldset className="city-master-fields" disabled={fieldsLocked}>
          <div className="city-master-row city-master-id-row">
            <span className="city-master-field-label">City ID</span>
            <div className="city-master-id-controls">
              <input
                className={`city-master-input city-master-id-input${mode === "add" ? " city-master-input-readonly" : ""}`}
                data-enter-order={1}
                readOnly={mode === "add"}
                value={cityCode}
                onChange={(event) => setCityCode(event.target.value)}
              />
              {mode === "modify" && (
                <button className="city-master-btn" type="button" onClick={() => void runFind()}>
                  Find (F5)
                </button>
              )}
            </div>
          </div>

          <div className="city-master-row">
            <span className="city-master-field-label">City</span>
            <input
              className="city-master-input"
              data-enter-order={2}
              value={cityName}
              onChange={(event) => setCityName(event.target.value)}
            />
          </div>

          <div className="city-master-row">
            <span className="city-master-field-label">District</span>
            <input
              className="city-master-input"
              data-enter-order={3}
              value={district}
              onChange={(event) => setDistrict(event.target.value)}
            />
          </div>

          <div className="city-master-row city-master-state-row">
            <span className="city-master-field-label">State</span>
            <input
              className="city-master-input city-master-state-input"
              data-enter-order={4}
              value={stateName}
              onChange={(event) => setStateName(event.target.value)}
            />
            <span className="city-master-inline-label">State Code</span>
            <input
              className="city-master-input city-master-state-code-input"
              data-enter-order={5}
              maxLength={4}
              value={stateCode}
              onChange={(event) => setStateCode(event.target.value)}
            />
          </div>

          <div className="city-master-row">
            <span className="city-master-field-label">Country</span>
            <input
              className="city-master-input"
              data-enter-order={6}
              value={country}
              onChange={(event) => setCountry(event.target.value)}
            />
          </div>

          <div className="city-master-row">
            <span className="city-master-field-label">Jurisdiction</span>
            <input
              className="city-master-input"
              data-enter-order={7}
              value={jurisdiction}
              onChange={(event) => setJurisdiction(event.target.value)}
            />
          </div>

          <div className="city-master-row">
            <span className="city-master-field-label">Focal Point</span>
            <select
              className="city-master-input city-master-select"
              data-enter-order={8}
              value={focalPoint}
              onChange={(event) =>
                setFocalPoint(event.target.value === "Y" ? "Y" : "N")
              }
            >
              {FOCAL_OPTIONS.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
        </fieldset>

        <div className="city-master-actions">
          {mode === "modify" && (
            <button
              className="city-master-btn city-master-btn-delete"
              disabled={!loaded}
              type="button"
              onClick={() => setDeleteOpen(true)}
            >
              Delete (F6)
            </button>
          )}
          <button
            className="city-master-btn city-master-btn-save"
            disabled={mode === "modify" && !loaded}
            type="submit"
          >
            Save (F3)
          </button>
          <button className="city-master-btn" type="button" onClick={onExit}>
            Cancel (F4)
          </button>
        </div>

        <footer className="city-master-status">
          {error ? <span className="city-master-error">{error}</span> : null}
          {!error && status ? <span className="city-master-ok">{status}</span> : null}
        </footer>
      </form>

      {findOpen && mode === "modify" && (
        <div className="city-master-find-overlay" role="presentation">
          <div className="city-master-find-panel" role="dialog" aria-modal="true">
            <header>
              <strong>Find City (F5)</strong>
              <button type="button" aria-label="Close" onClick={() => setFindOpen(false)}>
                ×
              </button>
            </header>
            <form
              className="city-master-find-search"
              onSubmit={(event) => {
                event.preventDefault();
                void runFind(findQuery);
              }}
            >
              <input
                placeholder="ID / city / district / state"
                value={findQuery}
                onChange={(event) => {
                  setFindQuery(event.target.value);
                  void refreshFindList(event.target.value);
                }}
              />
              <button type="submit">Search</button>
            </form>
            <div className="city-master-find-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>City</th>
                    <th>State</th>
                  </tr>
                </thead>
                <tbody>
                  {findRows.map((row) => (
                    <tr
                      key={String(row.city_id)}
                      tabIndex={0}
                      onDoubleClick={() => applyRecord(row)}
                    >
                      <td>{String(row.city_code ?? row.city_id ?? "")}</td>
                      <td>{String(row.name ?? "")}</td>
                      <td>{String(row.state_name ?? "")}</td>
                    </tr>
                  ))}
                  {!findRows.length && (
                    <tr>
                      <td colSpan={3}>No cities found.</td>
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
        recordLabel={cityName || "this city"}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => void confirmDelete()}
      />
    </>
  );
}
