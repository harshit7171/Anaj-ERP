import { FormEvent, useState } from "react";

import Autocomplete, { LookupItem } from "../Autocomplete";
import type { Result } from "../api/types";

type CompetitiveApi = {
  import_bank_statement(source: string, dryRun?: boolean): Promise<Result>;
  generate_reminder_letters(asOfDate: string, destination: string): Promise<Result>;
  print_cover_address(partyId: string, destination: string): Promise<Result>;
  blended_average_cost(
    commodityId: string,
    dateFrom: string,
    dateTo: string,
  ): Promise<Result>;
  open_whatsapp_url(url: string): Promise<Result>;
};

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function fyStart(): string {
  const now = new Date();
  const year = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1;
  return `${year}-04-01`;
}

export function BankReconciliation({ api }: { api: CompetitiveApi }) {
  const [path, setPath] = useState("");
  const [result, setResult] = useState<Result | null>(null);

  async function run(dryRun: boolean) {
    const response = await api.import_bank_statement(path, dryRun);
    setResult(response);
  }

  return (
    <section className="entry-form p-2 text-xs">
      <h2>Bank Statement Import (CSV)</h2>
      <p className="status-message">Columns: date, narration, amount (or debit/credit). Matches posted vouchers.</p>
      <label>
        File path
        <input className="w-full" value={path} onChange={(e) => setPath(e.target.value)} />
      </label>
      <div className="flex gap-2">
        <button type="button" onClick={() => void run(true)}>Preview Match</button>
        <button type="button" onClick={() => void run(false)}>Import & Match</button>
      </div>
      {result?.matched_count !== undefined && (
        <p>
          Matched: {String(result.matched_count)} · Unmatched: {String(result.unmatched_count)}
        </p>
      )}
      {result && <pre className="max-h-64 overflow-auto">{JSON.stringify(result, null, 2)}</pre>}
    </section>
  );
}

export function ReminderLetters({ api }: { api: CompetitiveApi }) {
  const [asOf, setAsOf] = useState(today());
  const [dest, setDest] = useState("C:\\AnajERP\\reminders.pdf");
  const [result, setResult] = useState<Result | null>(null);

  async function generate(event: FormEvent) {
    event.preventDefault();
    const response = await api.generate_reminder_letters(asOf, dest);
    setResult(response);
  }

  return (
    <form className="entry-form p-2 text-xs" onSubmit={(event) => void generate(event)}>
      <h2>Outstanding Reminder Letters (PDF)</h2>
      <label>
        As of
        <input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} />
      </label>
      <label>
        Save to
        <input value={dest} onChange={(e) => setDest(e.target.value)} />
      </label>
      <button type="submit">Generate PDF</button>
      {result?.ok && result.path ? <p>Saved: {String(result.path)}</p> : null}
    </form>
  );
}

export function CoverPrinting({ api }: { api: CompetitiveApi }) {
  const [party, setParty] = useState<LookupItem | null>(null);
  const [dest, setDest] = useState("C:\\AnajERP\\cover.pdf");
  const [result, setResult] = useState<Result | null>(null);

  async function print(event: FormEvent) {
    event.preventDefault();
    if (!party) return;
    const response = await api.print_cover_address(party.id, dest);
    setResult(response);
  }

  return (
    <form className="entry-form p-2 text-xs" onSubmit={(event) => void print(event)}>
      <h2>Cover / Envelope Printing</h2>
      <Autocomplete entityType="party" label="Recipient" value={party} onSelect={setParty} />
      <label>
        PDF path
        <input value={dest} onChange={(e) => setDest(e.target.value)} />
      </label>
      <button type="submit">Print Cover</button>
      {result && !result.ok && <p className="text-red-700">{result.error}</p>}
    </form>
  );
}

export function BlendedCostTool({ api }: { api: CompetitiveApi }) {
  const [commodity, setCommodity] = useState<LookupItem | null>(null);
  const [from, setFrom] = useState(fyStart());
  const [to, setTo] = useState(today());
  const [result, setResult] = useState<Result | null>(null);

  async function calculate(event: FormEvent) {
    event.preventDefault();
    if (!commodity) return;
    const response = await api.blended_average_cost(commodity.id, from, to);
    setResult(response);
  }

  const blended = result?.blended_rate_paise as number | undefined;

  return (
    <form className="entry-form p-2 text-xs" onSubmit={(event) => void calculate(event)}>
      <h2>Average Rate / Blended Cost</h2>
      <Autocomplete entityType="commodity" label="Crop / Item" value={commodity} onSelect={setCommodity} />
      <label>
        From
        <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
      </label>
      <label>
        To
        <input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
      </label>
      <button type="submit">Calculate</button>
      {blended !== undefined && (
        <p className="font-semibold">Blended rate: ₹{(blended / 100).toFixed(2)} per unit scale</p>
      )}
    </form>
  );
}

export function isCompetitiveTool(title: string): boolean {
  return (
    title === "Reminder Letters" ||
    title === "Cover Printing" ||
    title === "Blended Cost Calculator"
  );
}

export function CompetitiveToolRouter({ title, api }: { title: string; api: CompetitiveApi }) {
  if (title === "Reminder Letters") return <ReminderLetters api={api} />;
  if (title === "Cover Printing") return <CoverPrinting api={api} />;
  if (title === "Blended Cost Calculator") return <BlendedCostTool api={api} />;
  return null;
}
