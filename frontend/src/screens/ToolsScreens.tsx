import { FormEvent, useEffect, useMemo, useState } from "react";

import Autocomplete, { LookupItem } from "../Autocomplete";
import type { Result } from "../api/types";
import { fuzzyMatch } from "../utils/fuzzyFilter";
import PrintFormatDesigner from "./PrintFormatDesigner";
import UserAutomationSettings from "./UserAutomationSettings";
import CloudBackupSettings from "./CloudBackupSettings";
import { readAutomationFromSettings } from "./UserAutomationSettings";

type ToolsApi = {
  find_accounts(query?: string, city?: string, party_type?: string): Promise<Result & { rows?: Record<string, unknown>[] }>;
  whatsapp_payment_reminder?(partyId: string): Promise<Result & { url?: string }>;
  open_whatsapp_url?(url: string): Promise<Result>;
  save_stock_adjustment(payload: Record<string, unknown>): Promise<Result>;
  get_company_settings(): Promise<Result & { settings?: Record<string, unknown> }>;
  save_company_settings(settings: Record<string, unknown>): Promise<Result>;
  create_backup?(destination: string): Promise<Result>;
  list_prefix_settings(): Promise<Result & { prefixes?: Record<string, unknown>[] }>;
  save_prefix_setting(documentType: string, prefix: string, nextNumber: number): Promise<Result>;
  run_diagnostics(): Promise<Result & { diagnostics?: Record<string, unknown> }>;
  merge_parties(sourcePartyId: string, targetPartyId: string): Promise<Result>;
};

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export function FindAccountScreen({ api }: { api: ToolsApi }) {
  const [query, setQuery] = useState("");
  const [city, setCity] = useState("");
  const [partyType, setPartyType] = useState("");
  const [filter, setFilter] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [whatsappEnabled, setWhatsappEnabled] = useState(true);

  useEffect(() => {
    void api.get_company_settings().then((response) => {
      if (!response.ok) return;
      const automation = readAutomationFromSettings(response.settings);
      setWhatsappEnabled(automation.whatsapp_pending_balance);
    });
  }, [api]);

  async function remind(partyId: string) {
    const response = await api.whatsapp_payment_reminder?.(partyId);
    if (response?.ok && response.url) {
      await api.open_whatsapp_url?.(response.url);
    }
  }

  async function search(event: FormEvent) {
    event.preventDefault();
    const response = await api.find_accounts(query, city, partyType);
    setResult(response);
  }

  const rows: Record<string, unknown>[] = Array.isArray(result?.rows)
    ? (result.rows as Record<string, unknown>[])
    : [];
  const columns = rows.length ? Object.keys(rows[0]) : [];
  const filtered = useMemo(
    () =>
      rows.filter((row) =>
        fuzzyMatch(filter, columns.map((column) => String(row[column] ?? "")).join(" ")),
      ),
    [rows, columns, filter],
  );

  return (
    <section className="flex h-full min-h-0 flex-col overflow-hidden p-2">
      <h2 className="mb-2 text-sm font-semibold">Find Account</h2>
      <form className="mb-2 flex flex-wrap items-end gap-2 text-xs" onSubmit={(event) => void search(event)}>
        <label>
          Name / Phone / GSTIN
          <input className="rounded border px-1 py-0.5" value={query} onChange={(e) => setQuery(e.target.value)} />
        </label>
        <label>
          City
          <input className="rounded border px-1 py-0.5" value={city} onChange={(e) => setCity(e.target.value)} />
        </label>
        <label>
          Party type
          <input className="rounded border px-1 py-0.5" value={partyType} onChange={(e) => setPartyType(e.target.value)} />
        </label>
        <input
          className="rounded border px-2 py-0.5"
          placeholder="Filter results..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <button type="submit">Search</button>
      </form>
      {result && !result.ok && <p className="text-xs text-red-700">{result.error}</p>}
      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-full border-collapse text-xs">
          <thead>
            <tr>
              {columns.map((column) => (
                <th className="border px-1 py-0.5 text-left" key={column}>
                  {column.replaceAll("_", " ")}
                </th>
              ))}
              {whatsappEnabled ? <th className="border px-1 py-0.5">WhatsApp</th> : null}
            </tr>
          </thead>
          <tbody>
            {filtered.map((row, index) => (
              <tr key={index}>
                {columns.map((column) => (
                  <td className="border px-1 py-0.5" key={column}>
                    {String(row[column] ?? "")}
                  </td>
                ))}
                {whatsappEnabled && row.party_id ? (
                  <td className="border px-1 py-0.5">
                    <button type="button" onClick={() => void remind(String(row.party_id))}>
                      Remind
                    </button>
                  </td>
                ) : whatsappEnabled ? (
                  <td className="border px-1 py-0.5" />
                ) : null}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function StockAdjustmentScreen({ api }: { api: ToolsApi }) {
  const [date, setDate] = useState(today());
  const [refNo, setRefNo] = useState("");
  const [commodity, setCommodity] = useState<LookupItem | null>(null);
  const [adjustmentType, setAdjustmentType] = useState("increase");
  const [bags, setBags] = useState("0");
  const [quantity, setQuantity] = useState("0");
  const [remarks, setRemarks] = useState("");
  const [result, setResult] = useState<Result | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!commodity) {
      setResult({ ok: false, error: "Select a commodity." });
      return;
    }
    const response = await api.save_stock_adjustment({
      adjustment_date: date,
      ref_no: refNo,
      commodity_id: commodity.id,
      adjustment_type: adjustmentType,
      bags: Number(bags),
      quantity_scaled: Math.round(Number(quantity) * 1000),
      remarks,
    });
    setResult(response);
  }

  return (
    <form className="entry-form p-2 text-xs" onSubmit={(event) => void submit(event)}>
      <h2>Stock Adjustment</h2>
      <label>
        Date
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
      </label>
      <label>
        Ref No.
        <input value={refNo} onChange={(e) => setRefNo(e.target.value)} />
      </label>
      <Autocomplete entityType="commodity" label="Commodity" value={commodity} onSelect={setCommodity} />
      <label>
        Type
        <select value={adjustmentType} onChange={(e) => setAdjustmentType(e.target.value)}>
          <option value="increase">Increase</option>
          <option value="decrease">Decrease</option>
          <option value="wastage">Wastage</option>
        </select>
      </label>
      <label>
        Bags
        <input type="number" value={bags} onChange={(e) => setBags(e.target.value)} />
      </label>
      <label>
        Quantity (Qtl)
        <input type="number" step="0.001" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
      </label>
      <label>
        Remarks
        <input value={remarks} onChange={(e) => setRemarks(e.target.value)} />
      </label>
      <button type="submit">Save Adjustment</button>
      {result && (
        <p className={result.ok ? "text-green-800" : "text-red-700"}>
          {result.ok ? "Stock adjustment saved." : result.error}
        </p>
      )}
    </form>
  );
}

export function CompanyParametersScreen({ api }: { api: ToolsApi }) {
  const [gstin, setGstin] = useState("");
  const [legalName, setLegalName] = useState("");
  const [backupPath, setBackupPath] = useState("C:\\AnajERP\\backup");
  const [hideKachiDesktop, setHideKachiDesktop] = useState(false);
  const [gstLookupKey, setGstLookupKey] = useState("");
  const [gstLookupProvider, setGstLookupProvider] = useState("appyflow");
  const [industryMode, setIndustryMode] = useState("grain");
  const [arhatMode, setArhatMode] = useState("kachi");
  const [apmcState, setApmcState] = useState("haryana");
  const [managerPin, setManagerPin] = useState("");
  const [munimBackdateDays, setMunimBackdateDays] = useState("7");
  const [features, setFeatures] = useState({
    bardana_tracking: true,
    moisture_deduction: true,
    interest_on_advances: true,
    sms_whatsapp_dispatch: true,
  });
  const [baseSettings, setBaseSettings] = useState<Record<string, unknown>>({});
  const [result, setResult] = useState<Result | null>(null);

  useEffect(() => {
    void api.get_company_settings().then((response) => {
      if (!response.ok || !response.settings) return;
      const settings = response.settings;
      setBaseSettings(settings);
      setGstin(String(settings.gstin ?? ""));
      setLegalName(String(settings.legal_name ?? ""));
      const path = settings.default_backup_path;
      if (path) setBackupPath(String(path));
      setHideKachiDesktop(Boolean(settings.hide_kachi_on_this_pc));
      setGstLookupKey(String(settings.gst_lookup_api_key ?? ""));
      setGstLookupProvider(String(settings.gst_lookup_provider ?? "appyflow"));
      setIndustryMode(String(settings.industry_mode ?? "grain"));
      setArhatMode(String(settings.arhat_mode ?? "kachi"));
      setApmcState(String(settings.apmc_state ?? "haryana"));
      const feat = settings.features as Record<string, boolean> | undefined;
      if (feat) {
        setFeatures({
          bardana_tracking: Boolean(feat.bardana_tracking ?? true),
          moisture_deduction: Boolean(feat.moisture_deduction ?? true),
          interest_on_advances: Boolean(feat.interest_on_advances ?? true),
          sms_whatsapp_dispatch: Boolean(feat.sms_whatsapp_dispatch ?? true),
        });
      }
      const rbac = settings.rbac as Record<string, unknown> | undefined;
      if (rbac?.munim_backdate_days != null) {
        setMunimBackdateDays(String(rbac.munim_backdate_days));
      }
    });
  }, [api]);

  async function save(event: FormEvent) {
    event.preventDefault();
    localStorage.setItem("anajHideKachi", hideKachiDesktop ? "1" : "0");
    const response = await api.save_company_settings({
      ...baseSettings,
      gstin,
      legal_name: legalName,
      default_backup_path: backupPath,
      hide_kachi_on_this_pc: hideKachiDesktop,
      gst_lookup_api_key: gstLookupKey,
      gst_lookup_provider: gstLookupProvider,
      industry_mode: industryMode,
      arhat_mode: arhatMode,
      apmc_state: apmcState,
      features,
      rbac: {
        ...(typeof baseSettings.rbac === "object" ? (baseSettings.rbac as object) : {}),
        munim_backdate_days: Number(munimBackdateDays) || 7,
      },
      ...(managerPin.trim() ? { manager_override_pin: managerPin.trim() } : {}),
    });
    setResult(response);
  }

  return (
    <form className="entry-form p-2 text-xs" onSubmit={(event) => void save(event)}>
      <h2>Company Parameters</h2>
      <label>
        Legal name
        <input value={legalName} onChange={(e) => setLegalName(e.target.value)} />
      </label>
      <label>
        GSTIN
        <input maxLength={15} value={gstin} onChange={(e) => setGstin(e.target.value.toUpperCase())} />
      </label>
      <label>
        GST lookup API key (internet — AppyFlow or similar)
        <input value={gstLookupKey} onChange={(e) => setGstLookupKey(e.target.value)} />
      </label>
      <label>
        GST lookup provider
        <select value={gstLookupProvider} onChange={(e) => setGstLookupProvider(e.target.value)}>
          <option value="appyflow">AppyFlow (production API)</option>
          <option value="sandbox">GST sandbox gateway</option>
          <option value="custom">Custom URL template</option>
        </select>
      </label>
      <label>
        Default backup folder
        <input value={backupPath} onChange={(e) => setBackupPath(e.target.value)} />
      </label>
      <label className="checkbox-label">
        <input
          type="checkbox"
          checked={hideKachiDesktop}
          onChange={(e) => setHideKachiDesktop(e.target.checked)}
        />
        Hide Kachi companies on this PC (standalone / extra filter)
      </label>
      <h3 className="mt-3 font-semibold">Mandi mode &amp; features</h3>
      <label>
        Industry mode
        <select value={industryMode} onChange={(e) => setIndustryMode(e.target.value)}>
          <option value="grain">Grain (Qtl, moisture, bardana, mandi fees)</option>
          <option value="vegetable">Vegetable/Fruit (crates, boxes, kg)</option>
        </select>
      </label>
      <label>
        Arhat mode
        <select value={arhatMode} onChange={(e) => setArhatMode(e.target.value)}>
          <option value="kachi">Kachi (commission only)</option>
          <option value="pakki">Pakki (inventory risk)</option>
        </select>
      </label>
      <label>
        APMC schedule
        <select value={apmcState} onChange={(e) => setApmcState(e.target.value)}>
          <option value="haryana">Haryana HSAMB</option>
          <option value="punjab">Punjab PADB</option>
        </select>
      </label>
      <label>
        Munim backdate limit (days)
        <input type="number" min={0} value={munimBackdateDays} onChange={(e) => setMunimBackdateDays(e.target.value)} />
      </label>
      <label>
        Manager override PIN (credit limit)
        <input type="password" autoComplete="new-password" value={managerPin} onChange={(e) => setManagerPin(e.target.value)} placeholder="Leave blank to keep existing" />
      </label>
      {(
        [
          ["bardana_tracking", "Enable Bardana Tracking"],
          ["moisture_deduction", "Enable Moisture Deduction"],
          ["interest_on_advances", "Enable Interest on Advances"],
          ["sms_whatsapp_dispatch", "Enable SMS / WhatsApp Dispatch"],
        ] as const
      ).map(([key, label]) => (
        <label className="checkbox-label" key={key}>
          <input
            checked={features[key]}
            type="checkbox"
            onChange={() => setFeatures((current) => ({ ...current, [key]: !current[key] }))}
          />
          {label}
        </label>
      ))}
      <button type="submit">Save Parameters</button>
      {result && (
        <p className={result.ok ? "text-green-800" : "text-red-700"}>
          {result.ok ? "Parameters saved." : result.error}
        </p>
      )}
    </form>
  );
}

export function PrefixSettingsScreen({ api }: { api: ToolsApi }) {
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [documentType, setDocumentType] = useState("sale_invoice");
  const [prefix, setPrefix] = useState("");
  const [nextNumber, setNextNumber] = useState("1");
  const [result, setResult] = useState<Result | null>(null);

  async function refresh() {
    const response = await api.list_prefix_settings();
    if (response.ok && response.prefixes) setRows(response.prefixes);
  }

  useEffect(() => {
    void refresh();
  }, [api]);

  async function save(event: FormEvent) {
    event.preventDefault();
    const response = await api.save_prefix_setting(documentType, prefix, Number(nextNumber));
    setResult(response);
    if (response.ok) void refresh();
  }

  return (
    <section className="entry-form p-2 text-xs">
      <h2>Prefix Settings</h2>
      <form className="mb-3 flex flex-wrap items-end gap-2" onSubmit={(event) => void save(event)}>
        <label>
          Document type
          <input value={documentType} onChange={(e) => setDocumentType(e.target.value)} />
        </label>
        <label>
          Prefix
          <input value={prefix} onChange={(e) => setPrefix(e.target.value)} />
        </label>
        <label>
          Next number
          <input type="number" min={1} value={nextNumber} onChange={(e) => setNextNumber(e.target.value)} />
        </label>
        <button type="submit">Save</button>
      </form>
      {result && !result.ok && <p className="text-red-700">{result.error}</p>}
      <table className="w-full border-collapse text-xs">
        <thead>
          <tr>
            <th className="border px-1">Document type</th>
            <th className="border px-1">Prefix</th>
            <th className="border px-1">Next number</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              <td className="border px-1">{String(row.document_type ?? "")}</td>
              <td className="border px-1">{String(row.prefix ?? "")}</td>
              <td className="border px-1">{String(row.next_number ?? "")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export function DiagnosticsScreen({ api }: { api: ToolsApi }) {
  const [result, setResult] = useState<Result | null>(null);

  async function run() {
    const response = await api.run_diagnostics();
    setResult(response);
  }

  return (
    <section className="entry-form p-2 text-xs">
      <h2>System Diagnostics</h2>
      <p className="status-message">Runs reconciliation, trial balance check, and catalog metadata.</p>
      <button type="button" onClick={() => void run()}>
        Run Diagnostics
      </button>
      {result?.ok && result.diagnostics ? (
        <pre className="mt-2 max-h-96 overflow-auto rounded border bg-slate-50 p-2">
          {JSON.stringify(result.diagnostics, null, 2)}
        </pre>
      ) : null}
      {result && !result.ok && <p className="text-red-700">{result.error}</p>}
    </section>
  );
}

export function MergePartiesScreen({ api }: { api: ToolsApi }) {
  const [source, setSource] = useState<LookupItem | null>(null);
  const [target, setTarget] = useState<LookupItem | null>(null);
  const [result, setResult] = useState<Result | null>(null);

  async function merge(event: FormEvent) {
    event.preventDefault();
    if (!source || !target) {
      setResult({ ok: false, error: "Select source and target parties." });
      return;
    }
    const response = await api.merge_parties(source.id, target.id);
    setResult(response);
  }

  return (
    <form className="entry-form p-2 text-xs" onSubmit={(event) => void merge(event)}>
      <h2>Merge Parties</h2>
      <p className="status-message">Moves documents to the target party and deactivates the source.</p>
      <Autocomplete entityType="party" label="Source (duplicate)" value={source} onSelect={setSource} />
      <Autocomplete entityType="party" label="Target (keep)" value={target} onSelect={setTarget} />
      <button type="submit">Merge</button>
      {result && (
        <p className={result.ok ? "text-green-800" : "text-red-700"}>
          {result.ok ? "Parties merged." : result.error}
        </p>
      )}
    </form>
  );
}

export function isToolsScreen(title: string): boolean {
  return (
    title === "Company Parameters" ||
    title === "Prefix Settings" ||
    title === "System Diagnostics" ||
    title === "Merge Parties" ||
    title === "User Alerts & WhatsApp" ||
    title === "Google Drive Backup" ||
    title === "Cloud Backup" ||
    title === "Print Format Designer"
  );
}

export function ToolsScreenRouter({ title, api }: { title: string; api: ToolsApi }) {
  if (title === "Company Parameters") return <CompanyParametersScreen api={api} />;
  if (title === "Prefix Settings") return <PrefixSettingsScreen api={api} />;
  if (title === "System Diagnostics") return <DiagnosticsScreen api={api} />;
  if (title === "Merge Parties") return <MergePartiesScreen api={api} />;
  if (title === "User Alerts & WhatsApp") return <UserAutomationSettings api={api} />;
  if (title === "Google Drive Backup" || title === "Cloud Backup") {
    return <CloudBackupSettings api={api as never} />;
  }
  if (title === "Print Format Designer") return <PrintFormatDesigner api={api as never} />;
  return null;
}
