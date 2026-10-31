import { FormEvent, useEffect, useState } from "react";

type ApiResult = { ok: boolean; error?: string; path?: string; total?: number };

type SearchRow = {
  account_id: string;
  party_id: string;
  account_name: string;
  head: string;
  balance: string;
  aadhar_no: string;
  ac_code: string;
  bank_name: string;
  bank_ac_no: string;
  ifsc_code: string;
  address: string;
  city: string;
  contact: string;
};

type SearchApi = {
  search_accounts?(payload: Record<string, unknown>): Promise<ApiResult & { rows?: SearchRow[]; total?: number }>;
  export_account_search?(payload: Record<string, unknown>): Promise<ApiResult & { path?: string }>;
  copy_account_from_search?(account_id: string, copy_to_name: string): Promise<ApiResult>;
  whatsapp_payment_reminder?(partyId: string): Promise<ApiResult & { url?: string }>;
  open_whatsapp_url?(url: string): Promise<ApiResult>;
};

function bridge(): SearchApi | undefined {
  return window.pywebview?.api as unknown as SearchApi | undefined;
}

export default function FindAccountScreen({ onExit }: { onExit(): void }) {
  const [acName, setAcName] = useState("");
  const [mainHead, setMainHead] = useState("");
  const [contact, setContact] = useState("");
  const [city, setCity] = useState("");
  const [mobile, setMobile] = useState("");
  const [phone, setPhone] = useState("");
  const [gstNo, setGstNo] = useState("");
  const [panNo, setPanNo] = useState("");
  const [localCentral, setLocalCentral] = useState("N");
  const [gstType, setGstType] = useState("N");
  const [usageFilter, setUsageFilter] = useState("all");
  const [copyTo, setCopyTo] = useState("");
  const [rowLimit, setRowLimit] = useState("100");
  const [rows, setRows] = useState<SearchRow[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  function filters(): Record<string, unknown> {
    return {
      ac_name: acName,
      main_head: mainHead,
      contact,
      city,
      mobile,
      phone,
      gst_no: gstNo,
      pan_no: panNo,
      local_central: localCentral,
      gst_type: gstType,
      usage_filter: usageFilter,
      row_limit: Number(rowLimit) || 100,
    };
  }

  async function runSearch() {
    setError("");
    const response = await bridge()?.search_accounts?.(filters());
    if (!response?.ok) {
      setError(response?.error ?? "Search failed.");
      return;
    }
    setRows(response.rows ?? []);
    setTotal(response.total ?? response.rows?.length ?? 0);
    setStatus(`Total ${response.total ?? response.rows?.length ?? 0} records found`);
  }

  async function exportExcel() {
    const response = await bridge()?.export_account_search?.(filters());
    if (!response?.ok) setError(response?.error ?? "Export failed.");
    else setStatus(response.path ? `Exported: ${response.path}` : "Exported.");
  }

  async function copyAccount() {
    if (!selectedId || !copyTo.trim()) {
      setError("Select a row and enter Copy To name.");
      return;
    }
    const response = await bridge()?.copy_account_from_search?.(selectedId, copyTo.trim());
    if (!response?.ok) setError(response?.error ?? "Copy failed.");
    else {
      setStatus("Account copied.");
      void runSearch();
    }
  }

  useEffect(() => {
    void runSearch();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "F4") {
        event.preventDefault();
        onExit();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <section className="accounts-entry-screen find-account-screen">
      <header className="accounts-entry-title">Account Search ………(Total {total} records found)</header>
      <div className="accounts-entry-toolbar">
        <button type="button" onClick={() => void exportExcel()}>
          Export To Excel
        </button>
        <button type="button" onClick={() => void copyAccount()}>
          Copy Account
        </button>
        <button type="button" onClick={onExit}>
          Exit F4
        </button>
      </div>

      <form
        className="find-account-filters"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          void runSearch();
        }}
      >
        <label>
          Ac Name
          <input className="picker-field" value={acName} onChange={(e) => setAcName(e.target.value)} />
        </label>
        <label>
          Main Head
          <input value={mainHead} onChange={(e) => setMainHead(e.target.value)} />
        </label>
        <label>
          Contact
          <input value={contact} onChange={(e) => setContact(e.target.value)} />
        </label>
        <label>
          City
          <input value={city} onChange={(e) => setCity(e.target.value)} />
        </label>
        <label>
          Mobiles
          <input value={mobile} onChange={(e) => setMobile(e.target.value)} />
        </label>
        <label>
          Phone Nos
          <input value={phone} onChange={(e) => setPhone(e.target.value)} />
        </label>
        <label>
          Gst No
          <input value={gstNo} onChange={(e) => setGstNo(e.target.value)} />
        </label>
        <label>
          Pan No
          <input value={panNo} onChange={(e) => setPanNo(e.target.value)} />
        </label>
        <label>
          L/C/N
          <select value={localCentral} onChange={(e) => setLocalCentral(e.target.value)}>
            <option value="N">N</option>
            <option value="L">L</option>
            <option value="C">C</option>
          </select>
        </label>
        <label>
          Gst Type (R/U/C/N)
          <select value={gstType} onChange={(e) => setGstType(e.target.value)}>
            <option value="N">N</option>
            <option value="R">R</option>
            <option value="U">U</option>
            <option value="C">C</option>
          </select>
        </label>
        <label>
          Show Un-Used/Used/All Accounts
          <select value={usageFilter} onChange={(e) => setUsageFilter(e.target.value)}>
            <option value="all">All Accounts</option>
            <option value="used">Used</option>
            <option value="unused">Un-Used</option>
          </select>
        </label>
        <label>
          Copy To
          <input value={copyTo} onChange={(e) => setCopyTo(e.target.value)} />
        </label>
        <label>
          No of Rows
          <input inputMode="numeric" value={rowLimit} onChange={(e) => setRowLimit(e.target.value)} />
        </label>
        <button type="submit">Search</button>
      </form>

      <table className="accounts-entry-grid find-account-grid">
        <thead>
          <tr>
            <th />
            <th>Account Name</th>
            <th>Head</th>
            <th>Balance</th>
            <th>AadharNo</th>
            <th>AcCode</th>
            <th>BankName</th>
            <th>BankAcNo</th>
            <th>IFSCCode</th>
            <th>Address</th>
            <th>City</th>
            <th>Cont</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.account_id}
              className={selectedId === row.account_id ? "selected-row" : undefined}
              onClick={() => setSelectedId(row.account_id)}
            >
              <td>
                <input type="checkbox" checked={selectedId === row.account_id} readOnly />
              </td>
              <td>{row.account_name}</td>
              <td>{row.head}</td>
              <td className="numeric">{row.balance}</td>
              <td>{row.aadhar_no}</td>
              <td>{row.ac_code}</td>
              <td>{row.bank_name}</td>
              <td>{row.bank_ac_no}</td>
              <td>{row.ifsc_code}</td>
              <td>{row.address}</td>
              <td>{row.city}</td>
              <td>{row.contact}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {status && <p className="accounts-entry-status">{status}</p>}
      {error && <p className="accounts-entry-error">{error}</p>}
    </section>
  );
}
