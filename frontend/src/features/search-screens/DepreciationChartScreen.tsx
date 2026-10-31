import { useEffect, useState } from "react";

type ApiResult = { ok: boolean; error?: string };

type DepRow = {
  serial_no: number;
  account_name: string;
  opening_balance: string;
  depreciation_rate: string;
  depreciation_amount: string;
  closing_balance: string;
};

type DepApi = {
  depreciation_chart?(round_off: boolean): Promise<ApiResult & { rows?: DepRow[] }>;
  print_depreciation_chart?(round_off: boolean): Promise<ApiResult & { path?: string }>;
};

function bridge(): DepApi | undefined {
  return window.pywebview?.api as unknown as DepApi | undefined;
}

export default function DepreciationChartScreen({ onExit }: { onExit(): void }) {
  const [roundOff, setRoundOff] = useState(true);
  const [rows, setRows] = useState<DepRow[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  async function load(previewOnly: boolean) {
    setError("");
    const response = await bridge()?.depreciation_chart?.(roundOff);
    if (!response?.ok) {
      setError(response?.error ?? "Could not load chart.");
      return;
    }
    setRows(response.rows ?? []);
    setStatus(`${response.rows?.length ?? 0} account(s) with depreciation rate.`);
    if (!previewOnly) {
      const print = await bridge()?.print_depreciation_chart?.(roundOff);
      if (!print?.ok) setError(print?.error ?? "Print failed.");
      else setStatus("Sent to printer.");
    }
  }

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "F3") {
        event.preventDefault();
        void load(false);
      }
      if (event.key === "F4") {
        event.preventDefault();
        onExit();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [roundOff]);

  return (
    <section className="accounts-entry-screen depreciation-chart-screen">
      <header className="accounts-entry-title">Depriciation Chart</header>
      <div className="depreciation-toolbar">
        <label>
          Round Off
          <select className="picker-field" value={roundOff ? "Yes" : "No"} onChange={(e) => setRoundOff(e.target.value === "Yes")}>
            <option>Yes</option>
            <option>No</option>
          </select>
        </label>
        <button type="button" onClick={() => void load(true)}>
          Preview
        </button>
        <button type="button" className="accent-btn" onClick={() => void load(false)}>
          View F3
        </button>
        <button type="button" onClick={onExit}>
          Cancel F4
        </button>
      </div>

      <div className="depreciation-preview">
        <table className="accounts-entry-grid">
          <thead>
            <tr>
              <th>SNo</th>
              <th>Account</th>
              <th>Opening</th>
              <th>Rate %</th>
              <th>Depreciation</th>
              <th>Closing</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.serial_no}-${row.account_name}`}>
                <td>{row.serial_no}</td>
                <td>{row.account_name}</td>
                <td>{row.opening_balance}</td>
                <td>{row.depreciation_rate}</td>
                <td>{row.depreciation_amount}</td>
                <td>{row.closing_balance}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {status && <p className="accounts-entry-status">{status}</p>}
      {error && <p className="accounts-entry-error">{error}</p>}
    </section>
  );
}
