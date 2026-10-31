import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";

import Button from "../../components/Button";
import useFieldFocusHandlers from "../../hooks/useFieldFocusHandlers";
import { useFormEnterFlow } from "../../hooks/useFormEnterFlow";

import Autocomplete, { LookupItem } from "../../Autocomplete";
import CreditLimitWarningModal from "../../components/CreditLimitWarningModal";
import DataGrid from "../../components/DataGrid";
import TransactionScreen, { InlineField } from "../../components/TransactionScreen";
import type { CreditEvaluation } from "../../api/types";
import DenseDocumentForm, { supportsDenseDocument } from "../../DenseDocumentForm";
import { useGridEnterNavigation } from "../../hooks/useGridEnterNavigation";
import FarmerCreditDashboard from "../../screens/FarmerCreditDashboard";
import AccountMasterScreen from "../account-master/AccountMasterScreen";
import NarrationMasterScreen from "../narration-master/NarrationMasterScreen";
import CityMasterScreen from "../city-master/CityMasterScreen";
import TransportMasterScreen from "../transport-master/TransportMasterScreen";
import TradingAccountScreen from "../trading-account/TradingAccountScreen";
import ExpenseMasterScreen from "../expense-master/ExpenseMasterScreen";
import IFormExpenseScreen from "../i-form-expense-define/IFormExpenseScreen";
import ItemEntryScreen from "../item-entry/ItemEntryScreen";
import ChequePrintSettingScreen from "../cheque-print-setting/ChequePrintSettingScreen";
import BankMasterScreen from "../bank-master/BankMasterScreen";
import IfscMasterScreen from "../ifsc-master/IfscMasterScreen";
import StockEntryScreen from "../stock-entry-master/StockEntryScreen";
import { KachiPurchaseScreen } from "../kachi-purchase";
import { GstPurchaseEntryScreen } from "../gst-purchase-entry";
import { InvoiceEntryScreen } from "../invoice-entry";
import { GstDebitNoteEntryScreen } from "../gst-debit-note-entry";
import { GstCreditNoteEntryScreen } from "../gst-credit-note-entry";
import { GstExpenseVoucherEntryScreen } from "../gst-expense-voucher-entry";
import { CreditNoteEntryScreen, DebitNoteEntryScreen } from "../accounting-note-entry";
import { VoucherEntryScreen } from "../voucher-entry";
import { TdsChallanEntryScreen } from "../tds-challan-entry";
import { BankReconciliationScreen } from "../bank-reconciliation";
import {
  DepreciationChartScreen,
  FindAccountScreen,
  LetterHeadPrintScreen,
  StockAdjustmentScreen,
} from "../search-screens";
import { MandiPurchaseEntryScreen } from "../mandi-purchase-entry";
import { FormJEntryScreen } from "../form-j-entry";
import { LiftingEntryScreen } from "../lifting-entry";
import MasterForms from "../../screens/MasterForms";
import { isMasterWindow, resolveWindowTitle } from "../../app/routing/windowRouting";
import { isCatalogReport } from "../../app/routing/reportRegistry";
import { LegacyReportScreen } from "../reports";
import { GstReportScreen, isGstReportMenuTitle } from "../gst-reports";
import { isToolsScreen, ToolsScreenRouter } from "../../screens/ToolsScreens";
import UserAccessScreen from "../user-access/UserAccessScreen";
import {
  CompetitiveToolRouter,
  isCompetitiveTool,
} from "../../screens/CompetitiveTools";
import {
  IntegrationScreenRouter,
  isIntegrationScreen,
} from "../../screens/IntegrationScreens";
import GstRatesScreen from "../../screens/GstRatesScreen";
import { fuzzyMatch } from "../../utils/fuzzyFilter";

type Result = {
  ok: boolean;
  error?: string;
  error_type?: string;
  account?: Record<string, unknown>;
  commodity?: Record<string, unknown>;
  party?: Record<string, unknown>;
  voucher?: Record<string, unknown>;
  document?: Record<string, unknown>;
  calculation?: Record<string, unknown>;
  rows?: Record<string, unknown>[];
  path?: string;
  result?: Record<string, unknown>;
  conflicts?: Record<string, unknown>[];
  interest?: Record<string, unknown>;
  reconciliation?: Record<string, unknown>;
  migration?: Record<string, unknown>;
  document_number?: string;
  cash_book?: {
    closing_balance_paise?: number;
    receipts?: Record<string, unknown>[];
    payments?: Record<string, unknown>[];
  };
  submitted?: boolean;
};

type WorkflowApi = {
  create_account(name: string, accountType: string): Promise<Result>;
  create_party(payload: Record<string, unknown>): Promise<Result>;
  create_commodity(payload: Record<string, unknown>): Promise<Result>;
  create_charge_rule(payload: Record<string, unknown>): Promise<Result>;
  post_voucher(payload: Record<string, unknown>): Promise<Result>;
  calculate_document(payload: Record<string, unknown>): Promise<Result>;
  next_document_number(documentType: string): Promise<Result>;
  post_document(payload: Record<string, unknown>): Promise<Result>;
  trial_balance(): Promise<Result>;
  stock_balance(): Promise<Result>;
  cash_book(cashAccountId: string, dateFrom: string, dateTo: string): Promise<Result>;
  tax_register(dateFrom: string, dateTo: string, taxFamily: string): Promise<Result>;
  calculate_interest(
    accountId: string,
    dateFrom: string,
    dateTo: string,
    annualRate: string,
  ): Promise<Result>;
  create_invoice_pdf(
    documentId: string,
    destination: string,
    copyLabel: string,
  ): Promise<Result>;
  print_document(documentId: string): Promise<Result>;
  print_cash_book_register(cashAccountId: string, dateFrom: string, dateTo: string): Promise<Result>;
  print_day_book_register(dateFrom: string, dateTo: string): Promise<Result>;
  print_voucher(voucherId: string): Promise<Result>;
  run_diagnostics(): Promise<Result & { diagnostics?: Record<string, unknown> }>;
  merge_parties(sourcePartyId: string, targetPartyId: string): Promise<Result>;
  create_backup(destination: string): Promise<Result>;
  restore_new_company(source: string): Promise<Result>;
  reconcile_company(): Promise<Result>;
  import_master_csv(entityType: string, source: string, dryRun: boolean): Promise<Result>;
  check_credit_limit(payload: Record<string, unknown>): Promise<Result & { evaluation?: CreditEvaluation }>;
  list_agricultural_groups(): Promise<Result & { groups?: string[] }>;
  farmer_credit_dashboard(group?: string, query?: string): Promise<Result>;
  run_report(reportKey: string, params: Record<string, unknown>): Promise<Result>;
  find_accounts(query?: string, city?: string, party_type?: string): Promise<Result & { rows?: Record<string, unknown>[] }>;
  save_stock_adjustment(payload: Record<string, unknown>): Promise<Result>;
  get_company_settings(): Promise<Result & { settings?: Record<string, unknown> }>;
  save_company_settings(settings: Record<string, unknown>): Promise<Result>;
  list_prefix_settings(): Promise<Result & { prefixes?: Record<string, unknown>[] }>;
  save_prefix_setting(documentType: string, prefix: string, nextNumber: number): Promise<Result>;
  list_lan_users(): Promise<Result & { users?: Record<string, unknown>[] }>;
  save_lan_user(payload: Record<string, unknown>): Promise<Result>;
  set_company_profile(companyId: string, companyProfile: string): Promise<Result>;
  whatsapp_for_document(documentId: string): Promise<Result & { url?: string }>;
  whatsapp_payment_reminder(partyId: string): Promise<Result & { url?: string }>;
  open_whatsapp_url(url: string): Promise<Result>;
  generate_reminder_letters(asOfDate: string, destination: string): Promise<Result>;
  import_bank_statement(source: string, dryRun?: boolean): Promise<Result>;
  attach_document_file(documentId: string, source: string): Promise<Result>;
  list_document_attachments(documentId: string): Promise<Result & { attachments?: { attachment_id: string; file_name: string }[] }>;
  print_cover_address(partyId: string, destination: string): Promise<Result>;
  blended_average_cost(commodityId: string, dateFrom: string, dateTo: string): Promise<Result>;
};

function workflowApi(): WorkflowApi | undefined {
  return window.pywebview?.api as unknown as WorkflowApi | undefined;
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function rupeesToPaise(value: string): number {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return 0;
  return Math.round(amount * 100);
}

function buildChargeOverrides(
  calculation: Record<string, unknown> | null,
  rates: Record<string, string>,
) {
  const charges = (calculation?.charges ?? []) as Record<string, unknown>[];
  return Object.fromEntries(charges.flatMap((charge) => {
    const code = String(charge.code);
    const entered = rates[code];
    const original = Number(charge.rate_decimal);
    if (entered === undefined || Number(entered) === original || original === 0) return [];
    const automatic = Math.abs(Number(charge.automatic_amount_paise));
    return [[code, {
      amount_paise: Math.round(automatic * Number(entered || 0) / original),
      reason: "Operator adjusted rate before posting",
    }]];
  }));
}

function moveToNextField(event: KeyboardEvent<HTMLFormElement>) {
  if (event.key !== "Enter" || event.defaultPrevented) return;
  const target = event.target as HTMLElement;
  if (
    target.tagName === "TEXTAREA"
    || target.tagName === "BUTTON"
    || event.nativeEvent.isComposing
  ) return;
  event.preventDefault();
  const controls = Array.from(
    event.currentTarget.querySelectorAll<HTMLElement>(
      "input:not([disabled]), select:not([disabled]), textarea:not([disabled])",
    ),
  ).filter((control) => control.offsetParent !== null);
  const index = controls.indexOf(target);
  const next = controls[index + 1];
  if (next) {
    next.focus();
    next.scrollIntoView({ block: "nearest" });
  } else {
    event.currentTarget.requestSubmit();
  }
}

function Message({ result }: { result: Result | null }) {
  const [dismissed, setDismissed] = useState(false);
  useEffect(() => setDismissed(false), [result]);
  if (!result) return null;
  if (
    !result.ok
    && !dismissed
    && ["ClockTamperException", "LicenseWriteLockedError"].includes(result.error_type ?? "")
  ) {
    const tamper = result.error_type === "ClockTamperException";
    return (
      <div className="blocking-modal license-blocker" role="alertdialog" aria-modal="true">
        <div className="saved-dialog">
          <header><span>Anaj Accounting ERP</span></header>
          <p>{result.error}</p>
          {!tamper && <button type="button" onClick={() => setDismissed(true)}>Close</button>}
        </div>
      </div>
    );
  }
  return (
    <p className={result.ok ? "success-message" : "error-message"}>
      {result.ok ? "Saved successfully." : result.error}
    </p>
  );
}

function SavedModal({ onClose }: { onClose(): void }) {
  return (
    <div className="blocking-modal" role="dialog" aria-modal="true" aria-labelledby="saved-title">
      <div className="saved-dialog">
        <header>
          <span id="saved-title">Anaj Accounting ERP</span>
          <button aria-label="Close" type="button" onClick={onClose}>×</button>
        </header>
        <p>Data has been Successfully Saved</p>
        <button autoFocus type="button" onClick={onClose}>Close</button>
      </div>
    </div>
  );
}

function LedgerForm() {
  const [name, setName] = useState("");
  const [type, setType] = useState("asset");
  const [result, setResult] = useState<Result | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const response = await workflowApi()?.create_account(name, type);
    if (response) {
      setResult(response);
      if (response.ok) setName("");
    }
  }

  return (
    <form className="entry-form" onKeyDown={moveToNextField} onSubmit={(e) => void submit(e)}>
      <h2>New Ledger</h2>
      <label>
        Account Name
        <input autoFocus required value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <label>
        Account Type
        <select value={type} onChange={(e) => setType(e.target.value)}>
          {["asset", "liability", "income", "expense", "capital", "cash", "bank", "party"].map(
            (item) => <option key={item}>{item}</option>,
          )}
        </select>
      </label>
      <button type="submit">Save</button>
      <Message result={result} />
    </form>
  );
}

function CommodityForm() {
  const [name, setName] = useState("");
  const [variety, setVariety] = useState("");
  const [hsn, setHsn] = useState("");
  const [bagWeight, setBagWeight] = useState("");
  const [result, setResult] = useState<Result | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const response = await workflowApi()?.create_commodity({
      name,
      variety,
      hsn_code: hsn,
      quantity_scale: 3,
      standard_bag_weight_scaled: bagWeight
        ? Math.round(Number(bagWeight) * 1000)
        : null,
    });
    if (response) setResult(response);
  }

  return (
    <form className="entry-form" onKeyDown={moveToNextField} onSubmit={(e) => void submit(e)}>
      <h2>New Commodity</h2>
      <label>Commodity<input autoFocus required value={name} onChange={(e) => setName(e.target.value)} /></label>
      <label>Variety<input value={variety} onChange={(e) => setVariety(e.target.value)} /></label>
      <label>HSN Code<input value={hsn} onChange={(e) => setHsn(e.target.value)} /></label>
      <label>Standard Bag Weight<input type="number" step="0.001" value={bagWeight} onChange={(e) => setBagWeight(e.target.value)} /></label>
      <button type="submit">Save</button>
      <Message result={result} />
    </form>
  );
}

function PartyForm() {
  const [name, setName] = useState("");
  const [partyType, setPartyType] = useState("farmer");
  const [fatherName, setFatherName] = useState("");
  const [agriculturalGroup, setAgriculturalGroup] = useState("");
  const [villageName, setVillageName] = useState("");
  const [creditLimit, setCreditLimit] = useState("");
  const [groups, setGroups] = useState<string[]>([]);
  const [gstin, setGstin] = useState("");
  const [pan, setPan] = useState("");
  const [address, setAddress] = useState("");
  const [result, setResult] = useState<Result | null>(null);

  useEffect(() => {
    void workflowApi()?.list_agricultural_groups().then((response) => {
      if (response?.ok) setGroups(response.groups ?? []);
    });
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const response = await workflowApi()?.create_party({
      name,
      party_type: partyType,
      father_name: fatherName,
      related_name: fatherName,
      agricultural_group: agriculturalGroup,
      village_name: villageName,
      credit_limit_paise: rupeesToPaise(creditLimit),
      gstin,
      pan,
      address,
    });
    if (response) setResult(response);
  }

  return (
    <form className="entry-form dense-party-form" onKeyDown={moveToNextField} onSubmit={(e) => void submit(e)}>
      <h2>Farmer / Party Master</h2>
      <div className="dense-header-row">
        <label>Farmer Name<input autoFocus required value={name} onChange={(e) => setName(e.target.value)} /></label>
        <label>S/O / Father Name<input value={fatherName} onChange={(e) => setFatherName(e.target.value)} /></label>
        <label>Agricultural Group
          <input list="agricultural-groups" value={agriculturalGroup} onChange={(e) => setAgriculturalGroup(e.target.value)} />
          <datalist id="agricultural-groups">{groups.map((group) => <option key={group} value={group} />)}</datalist>
        </label>
        <label>Village<input value={villageName} onChange={(e) => setVillageName(e.target.value)} /></label>
      </div>
      <div className="dense-header-row">
        <label>Party Type<select value={partyType} onChange={(e) => setPartyType(e.target.value)}>
          {["farmer", "customer", "supplier", "purchaser", "commission_agent", "transporter"].map(
            (item) => <option key={item}>{item}</option>,
          )}
        </select></label>
        <label>Max Borrowing Limit (₹)<input inputMode="decimal" placeholder="0 = not set" value={creditLimit} onChange={(e) => setCreditLimit(e.target.value)} /></label>
        <label>GSTIN<input maxLength={15} value={gstin} onChange={(e) => setGstin(e.target.value.toUpperCase())} /></label>
        <label>PAN<input maxLength={10} value={pan} onChange={(e) => setPan(e.target.value.toUpperCase())} /></label>
      </div>
      <label>Address<textarea value={address} onChange={(e) => setAddress(e.target.value)} /></label>
      <button type="submit">Save</button>
      <Message result={result} />
    </form>
  );
}

type VoucherEntryRow = {
  rowId: number;
  entryType: "Dr" | "Cr";
  account: LookupItem | null;
  debit: string;
  credit: string;
  remarks: string;
};

function newVoucherEntryRow(rowId: number): VoucherEntryRow {
  return { rowId, entryType: rowId % 2 ? "Dr" : "Cr", account: null, debit: "", credit: "", remarks: "" };
}

function JournalForm({ kind, onExit }: { kind: string; onExit(): void }) {
  const [number, setNumber] = useState("");
  const [date, setDate] = useState(today());
  const [voucherType, setVoucherType] = useState(
    kind === "Accounting Voucher" ? "Journal" : kind,
  );
  const [referenceDocument, setReferenceDocument] = useState("");
  const [rows, setRows] = useState<VoucherEntryRow[]>([
    newVoucherEntryRow(1),
    newVoucherEntryRow(2),
  ]);
  const [result, setResult] = useState<Result | null>(null);
  const [showSavedModal, setShowSavedModal] = useState(false);
  const [lastVoucherId, setLastVoucherId] = useState("");
  const [creditWarning, setCreditWarning] = useState<CreditEvaluation | null>(null);
  const [creditOverride, setCreditOverride] = useState(false);
  const [managerOverridePin, setManagerOverridePin] = useState("");

  function updateRow(rowId: number, values: Partial<VoucherEntryRow>) {
    setRows((current) =>
      current.map((row) => (row.rowId === rowId ? { ...row, ...values } : row)),
    );
  }

  function appendRow() {
    setRows((current) => {
      const next = [...current, newVoucherEntryRow(Math.max(...current.map((row) => row.rowId)) + 1)];
      window.setTimeout(() => {
        document.querySelector<HTMLElement>(
          `[data-grid-row]:last-of-type input`,
        )?.focus();
      }, 0);
      return next;
    });
  }

  async function submit(event: FormEvent, forceOverride = false) {
    event.preventDefault();
    const completeRows = rows.filter(
      (row) => row.account && (rupeesToPaise(row.debit) || rupeesToPaise(row.credit)),
    );
    if (completeRows.length < 2) {
      setResult({ ok: false, error: "Enter at least two ledger lines." });
      return;
    }
    if (completeRows.some((row) => rupeesToPaise(row.debit) && rupeesToPaise(row.credit))) {
      setResult({ ok: false, error: "A journal row cannot contain both debit and credit." });
      return;
    }
    const debitTotal = completeRows.reduce((sum, row) => sum + rupeesToPaise(row.debit), 0);
    const creditTotal = completeRows.reduce((sum, row) => sum + rupeesToPaise(row.credit), 0);
    if (debitTotal !== creditTotal) {
      setResult({ ok: false, error: "Debit and credit totals must be equal." });
      return;
    }
    if (!forceOverride && !creditOverride) {
      for (const row of completeRows) {
        if (row.entryType !== "Dr" || !row.account?.id) continue;
        const debit = rupeesToPaise(row.debit);
        if (!debit) continue;
        const preview = await workflowApi()?.check_credit_limit({
          account_id: row.account.id,
          additional_debit_paise: debit,
        });
        if (preview?.evaluation?.breached) {
          setCreditWarning(preview.evaluation);
          return;
        }
      }
    }
    const response = await workflowApi()?.post_voucher({
      voucher_type: voucherType.toLowerCase().replaceAll(" ", "_"),
      voucher_number: number,
      voucher_date: date,
      credit_override_confirmed: forceOverride || creditOverride,
      manager_override_pin: managerOverridePin,
      narration: [
        referenceDocument ? `Reference: ${referenceDocument}` : "",
        ...completeRows.map((row) => row.remarks),
      ].filter(Boolean).join("; "),
      lines: completeRows.map((row) => ({
        account_id: row.account?.id,
        debit_paise: row.entryType === "Dr" ? rupeesToPaise(row.debit) : 0,
        credit_paise: row.entryType === "Cr" ? rupeesToPaise(row.credit) : 0,
        narration: row.remarks,
      })),
    });
    if (response) {
      setResult(response);
      if (response.ok) {
        setShowSavedModal(true);
        const voucherId = String((response.voucher as { voucher_id?: string } | undefined)?.voucher_id ?? "");
        if (voucherId) setLastVoucherId(voucherId);
      }
    }
  }

  async function printVoucher() {
    if (!lastVoucherId) {
      setResult({ ok: false, error: "Save the voucher before printing." });
      return;
    }
    const response = await workflowApi()?.print_voucher(lastVoucherId);
    if (response) setResult(response);
  }

  const debitTotal = rows.reduce((sum, row) => sum + rupeesToPaise(row.debit), 0);
  const creditTotal = rows.reduce((sum, row) => sum + rupeesToPaise(row.credit), 0);

  return (
    <>
      <TransactionScreen
        title={kind}
        header={(
          <>
            <InlineField label="Voucher No.">
              <input autoFocus required className="w-full rounded border px-1 py-0.5" value={number} onChange={(event) => setNumber(event.target.value)} />
            </InlineField>
            <InlineField label="Date">
              <input required type="date" className="w-full rounded border px-1 py-0.5" value={date} onChange={(event) => setDate(event.target.value)} />
            </InlineField>
            <InlineField label="Type">
              <select className="w-full rounded border px-1 py-0.5" value={voucherType} onChange={(event) => setVoucherType(event.target.value)}>
                <option>Receipt</option><option>Payment</option><option>Journal</option><option>Contra</option>
              </select>
            </InlineField>
            <InlineField label="Reference">
              <input className="w-full rounded border px-1 py-0.5" value={referenceDocument} onChange={(event) => setReferenceDocument(event.target.value)} />
            </InlineField>
          </>
        )}
        grid={(
          <DataGrid onRowComplete={appendRow}>
            <colgroup>
              <col className="w-[10%]" />
              <col className="w-[27%]" />
              <col className="w-[17%]" />
              <col className="w-[17%]" />
              <col className="w-[25%]" />
              <col className="w-[4%]" />
            </colgroup>
            <thead>
              <tr className="text-left">
                <th className="border px-1">Type</th>
                <th className="border px-1">Ledger Account</th>
                <th className="border px-1">Debit</th>
                <th className="border px-1">Credit</th>
                <th className="border px-1">Narration</th>
                <th className="border px-1" />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr className="border-b" data-grid-row key={row.rowId}>
                  <td className="border px-1">
                    <select className="w-full" value={row.entryType} onChange={(event) => updateRow(row.rowId, {
                      entryType: event.target.value as "Dr" | "Cr",
                      debit: event.target.value === "Dr" ? row.debit : "",
                      credit: event.target.value === "Cr" ? row.credit : "",
                    })}><option>Dr</option><option>Cr</option></select>
                  </td>
                  <td className="border px-1"><Autocomplete entityType="account" label="" value={row.account} onSelect={(value) => updateRow(row.rowId, { account: value })} /></td>
                  <td className="border px-1"><input className="w-full tabular-nums" disabled={row.entryType !== "Dr"} inputMode="numeric" value={row.debit} onChange={(event) => updateRow(row.rowId, { debit: event.target.value })} /></td>
                  <td className="border px-1"><input className="w-full tabular-nums" disabled={row.entryType !== "Cr"} inputMode="numeric" value={row.credit} onChange={(event) => updateRow(row.rowId, { credit: event.target.value })} /></td>
                  <td className="border px-1"><input className="w-full" value={row.remarks} onChange={(event) => updateRow(row.rowId, { remarks: event.target.value })} /></td>
                  <td className="border px-1">
                    <button aria-label="Remove row" disabled={rows.length === 2} type="button" onClick={() => setRows((current) => current.filter((item) => item.rowId !== row.rowId))}>×</button>
                  </td>
                </tr>
              ))}
              <tr className="font-medium">
                <td className="border px-1" colSpan={2}>Total</td>
                <td className="border px-1 tabular-nums">₹{(debitTotal / 100).toFixed(2)}</td>
                <td className="border px-1 tabular-nums">₹{(creditTotal / 100).toFixed(2)}</td>
                <td className="border px-1" colSpan={2}>
                  <button type="button" onClick={appendRow}>Add Row</button>
                </td>
              </tr>
            </tbody>
          </DataGrid>
        )}
        footerMessage={<Message result={result} />}
        onSave={(event) => void submit(event)}
        onPrint={() => void printVoucher()}
        onExit={onExit}
      />
      {creditWarning && (
        <CreditLimitWarningModal
          evaluation={creditWarning}
          onCancel={() => setCreditWarning(null)}
          onProceed={(pin) => {
            setCreditOverride(true);
            setManagerOverridePin(pin);
            setCreditWarning(null);
            void submit({ preventDefault() {} } as FormEvent, true);
          }}
        />
      )}
      {showSavedModal && <SavedModal onClose={() => setShowSavedModal(false)} />}
    </>
  );
}

type CashEntryRow = {
  rowId: number;
  account: LookupItem | null;
  amount: string;
  remarks: string;
};

function newCashEntryRow(rowId: number): CashEntryRow {
  return { rowId, account: null, amount: "", remarks: "" };
}

function financialYearStart(value: string): string {
  const selected = new Date(`${value}T00:00:00`);
  const year = selected.getMonth() >= 3 ? selected.getFullYear() : selected.getFullYear() - 1;
  return `${year}-04-01`;
}

function CashBookForm({ onExit }: { onExit(): void }) {
  const [number, setNumber] = useState("");
  const [date, setDate] = useState(today());
  const [cashAccount, setCashAccount] = useState<LookupItem | null>(null);
  const [receipts, setReceipts] = useState<CashEntryRow[]>([newCashEntryRow(1)]);
  const [payments, setPayments] = useState<CashEntryRow[]>([newCashEntryRow(1)]);
  const [cashInHand, setCashInHand] = useState(0);
  const [result, setResult] = useState<Result | null>(null);
  const [showSavedModal, setShowSavedModal] = useState(false);
  const [lastVoucherId, setLastVoucherId] = useState("");
  const [activeSide, setActiveSide] = useState<"receipt" | "payment">("receipt");

  useEffect(() => {
    if (!cashAccount) {
      setCashInHand(0);
      return;
    }
    void workflowApi()?.cash_book(
      cashAccount.id,
      financialYearStart(date),
      date,
    ).then((response) => {
      if (response.ok) {
        setCashInHand(Number(response.cash_book?.closing_balance_paise ?? 0));
      }
    });
  }, [cashAccount, date]);

  function updateCashRow(
    side: "receipt" | "payment",
    rowId: number,
    values: Partial<CashEntryRow>,
  ) {
    const setter = side === "receipt" ? setReceipts : setPayments;
    setter((current) =>
      current.map((row) => (row.rowId === rowId ? { ...row, ...values } : row)),
    );
  }

  function appendCashRow(side: "receipt" | "payment" = activeSide) {
    setActiveSide(side);
    const setter = side === "receipt" ? setReceipts : setPayments;
    setter((current) => {
      const next = [...current, newCashEntryRow(Math.max(...current.map((row) => row.rowId)) + 1)];
      window.setTimeout(() => {
        document.querySelector<HTMLElement>(
          `[data-cash-side="${side}"] [data-grid-row]:last-of-type input`,
        )?.focus();
      }, 0);
      return next;
    });
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!cashAccount) {
      setResult({ ok: false, error: "Select the Cash in Hand account." });
      return;
    }
    const receiptRows = receipts.filter((row) => row.account && rupeesToPaise(row.amount));
    const paymentRows = payments.filter((row) => row.account && rupeesToPaise(row.amount));
    if (!receiptRows.length && !paymentRows.length) {
      setResult({ ok: false, error: "Enter at least one receipt or payment." });
      return;
    }
    if ([...receiptRows, ...paymentRows].some((row) => row.account?.id === cashAccount.id)) {
      setResult({ ok: false, error: "Particulars cannot use the selected cash account." });
      return;
    }
    const receiptTotal = receiptRows.reduce((sum, row) => sum + rupeesToPaise(row.amount), 0);
    const paymentTotal = paymentRows.reduce((sum, row) => sum + rupeesToPaise(row.amount), 0);
    const lines = [
      ...receiptRows.map((row) => ({
        account_id: row.account?.id,
        debit_paise: 0,
        credit_paise: rupeesToPaise(row.amount),
        narration: row.remarks,
      })),
      ...paymentRows.map((row) => ({
        account_id: row.account?.id,
        debit_paise: rupeesToPaise(row.amount),
        credit_paise: 0,
        narration: row.remarks,
      })),
      ...(receiptTotal ? [{ account_id: cashAccount.id, debit_paise: receiptTotal, credit_paise: 0 }] : []),
      ...(paymentTotal ? [{ account_id: cashAccount.id, debit_paise: 0, credit_paise: paymentTotal }] : []),
    ];
    const response = await workflowApi()?.post_voucher({
      voucher_type: "cash_book",
      voucher_number: number,
      voucher_date: date,
      narration: "Cash Book entry",
      lines,
    });
    if (response) {
      setResult(response);
      if (response.ok) {
        setCashInHand((value) => value + receiptTotal - paymentTotal);
        setShowSavedModal(true);
        const voucherId = String((response.voucher as { voucher_id?: string } | undefined)?.voucher_id ?? "");
        if (voucherId) setLastVoucherId(voucherId);
      }
    }
  }

  async function printRegister() {
    if (!cashAccount) {
      setResult({ ok: false, error: "Select the Cash in Hand account." });
      return;
    }
    const response = await workflowApi()?.print_cash_book_register(
      cashAccount.id,
      financialYearStart(date),
      date,
    );
    if (response) setResult(response);
  }

  async function printLastVoucher() {
    if (!lastVoucherId) {
      setResult({ ok: false, error: "Save the cash book entry before printing the voucher." });
      return;
    }
    const response = await workflowApi()?.print_voucher(lastVoucherId);
    if (response) setResult(response);
  }

  function cashTable(
    side: "receipt" | "payment",
    rows: CashEntryRow[],
  ) {
    const amountHeading = side === "receipt" ? "Amount (Cr.)" : "Amount (Dr.)";
    return (
      <section data-cash-side={side} onFocusCapture={() => setActiveSide(side)}>
        <h3 className="mb-1 font-semibold">{side === "receipt" ? "Receipts" : "Payments"}</h3>
        <DataGrid onRowComplete={() => appendCashRow(side)}>
          <thead>
            <tr className="text-left">
              <th className="border px-1">Particulars</th>
              <th className="border px-1">{amountHeading}</th>
              <th className="border px-1">Remarks</th>
              <th className="border px-1" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr className="border-b" data-grid-row key={row.rowId}>
                <td className="border px-1">
                  <Autocomplete entityType="account" label="" value={row.account} onSelect={(value) => updateCashRow(side, row.rowId, { account: value })} />
                </td>
                <td className="border px-1">
                  <input className="w-full tabular-nums" inputMode="decimal" value={row.amount} onChange={(event) => updateCashRow(side, row.rowId, { amount: event.target.value })} />
                </td>
                <td className="border px-1">
                  <input className="w-full" value={row.remarks} onChange={(event) => updateCashRow(side, row.rowId, { remarks: event.target.value })} />
                </td>
                <td className="border px-1">
                  <button disabled={rows.length === 1} type="button" onClick={() => {
                    const setter = side === "receipt" ? setReceipts : setPayments;
                    setter((current) => current.filter((item) => item.rowId !== row.rowId));
                  }}>×</button>
                </td>
              </tr>
            ))}
          </tbody>
        </DataGrid>
        <button className="mt-1" type="button" onClick={() => appendCashRow(side)}>Add Row</button>
      </section>
    );
  }

  return (
    <>
      <TransactionScreen
        title="Cash Book"
        header={(
          <>
            <InlineField label="Voucher No.">
              <input autoFocus required className="w-full rounded border px-1 py-0.5" value={number} onChange={(event) => setNumber(event.target.value)} />
            </InlineField>
            <InlineField label="Date">
              <input required type="date" className="w-full rounded border px-1 py-0.5" value={date} onChange={(event) => setDate(event.target.value)} />
            </InlineField>
            <div className="min-w-[220px]">
              <Autocomplete entityType="account" label="Cash in Hand" required value={cashAccount} onSelect={setCashAccount} />
            </div>
            <div className="tabular-nums text-[11px] font-semibold text-accent">
              Cash in Hand: ₹{(cashInHand / 100).toFixed(2)}
            </div>
          </>
        )}
        grid={(
          <div className="cash-book-tables-grid grid min-h-0 grid-cols-2 gap-3">
            {cashTable("receipt", receipts)}
            {cashTable("payment", payments)}
          </div>
        )}
        footerMessage={<Message result={result} />}
        onSave={(event) => void submit(event)}
        onPrint={() => void (lastVoucherId ? printLastVoucher() : printRegister())}
        onExit={onExit}
      />
      {showSavedModal && <SavedModal onClose={() => setShowSavedModal(false)} />}
    </>
  );
}

const documentTypes: Record<string, string> = {
  "Form - J": "form_j",
  "Form - I (Dr.)": "form_i_debit",
  "Form - I (Cr.)": "form_i_credit",
  "Transfer Challan": "transfer_challan",
  "Sale Invoice": "sale_invoice",
  "Purchase Invoice": "purchase_invoice",
  "Delivery Challan": "delivery_challan",
  "Gate Pass": "gate_pass",
  "Sale Memo": "sale_memo",
  "Purchase Memo": "purchase_memo",
  "Inward": "inward",
  "Outward": "outward",
  "Consignment (Dr.)": "consignment_debit",
  "Consignment (Cr.)": "consignment_credit",
  "Milling Inward": "milling_inward",
  "Milling Outward": "milling_outward",
  "Packing Material Transfer": "packing_material_transfer",
};

type SaleBillRow = {
  rowId: number;
  commodity: LookupItem | null;
  sourceNumber: string;
  commissionAgent: LookupItem | null;
  bags: string;
  pack: string;
  extra: string;
  rate: string;
};

function newSaleBillRow(rowId: number): SaleBillRow {
  return {
    rowId,
    commodity: null,
    sourceNumber: "",
    commissionAgent: null,
    bags: "",
    pack: "50",
    extra: "",
    rate: "",
  };
}

function saleBillQuantity(row: SaleBillRow): number {
  return ((Number(row.bags || 0) * Number(row.pack || 0)) + Number(row.extra || 0)) / 100;
}

function MandiVoucherActions({
  onCalculate,
  onPrint,
  postedId,
  onExit,
}: {
  onCalculate(): void;
  onPrint?(): void;
  postedId: string;
  onExit(): void;
}) {
  return (
    <div className="form-actions mandi-form-actions">
      <Button type="button" variant="alert" onClick={onCalculate}>
        Calculate
      </Button>
      <Button disabled={!postedId} type="button" variant="print" onClick={onPrint}>
        Print
      </Button>
      <Button type="submit" variant="save">
        Save
      </Button>
      <Button className="btn-tactile-exit" type="button" variant="secondary" onClick={onExit}>
        Exit
      </Button>
    </div>
  );
}

function SaleBill({ title, onExit }: { title: string; onExit(): void }) {
  const formRef = useRef<HTMLFormElement>(null);
  useFormEnterFlow(formRef);
  useFieldFocusHandlers(formRef);
  const type = title === "Form - I (Dr.)" ? "form_i_debit" : "sale_invoice";
  const [number, setNumber] = useState("");
  const [date, setDate] = useState(today());
  const [dueDate, setDueDate] = useState(today());
  const [party, setParty] = useState<LookupItem | null>(null);
  const [partyAccount, setPartyAccount] = useState<LookupItem | null>(null);
  const [saleAccount, setSaleAccount] = useState<LookupItem | null>(null);
  const [cashAccount, setCashAccount] = useState<LookupItem | null>(null);
  const [rows, setRows] = useState<SaleBillRow[]>([newSaleBillRow(1)]);
  const [vehicle, setVehicle] = useState("");
  const [grNumber, setGrNumber] = useState("");
  const [grDate, setGrDate] = useState(today());
  const [dispatchTime, setDispatchTime] = useState(
    new Date().toTimeString().slice(0, 5),
  );
  const [eway, setEway] = useState("");
  const [deliverAt, setDeliverAt] = useState("");
  const [freight, setFreight] = useState("");
  const [freightDirection, setFreightDirection] = useState("add");
  const [advance, setAdvance] = useState("");
  const [remarks, setRemarks] = useState("");
  const [insurance, setInsurance] = useState("");
  const [packingTransfer, setPackingTransfer] = useState(false);
  const [stockSale, setStockSale] = useState(true);
  const [multiTax, setMultiTax] = useState(false);
  const [excludedCharges, setExcludedCharges] = useState<string[]>([]);
  const [rateOverrides, setRateOverrides] = useState<Record<string, string>>({});
  const [calculation, setCalculation] = useState<Record<string, unknown> | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [postedId, setPostedId] = useState("");
  const [showSavedModal, setShowSavedModal] = useState(false);

  useEffect(() => {
    void workflowApi()?.next_document_number(type).then((response) => {
      if (response.document_number) setNumber(response.document_number);
    });
  }, [type]);

  function selectParty(value: LookupItem | null) {
    setParty(value);
    if (value?.account_id && value.account_name) {
      setPartyAccount({ id: value.account_id, label: value.account_name });
    }
    if (value?.address && !deliverAt) {
      setDeliverAt(value.address.split(",").at(-1)?.trim() ?? "");
    }
  }

  function updateRow(rowId: number, values: Partial<SaleBillRow>) {
    setRows((current) =>
      current.map((row) => (row.rowId === rowId ? { ...row, ...values } : row)),
    );
  }

  function appendSaleRow() {
    setRows((current) => [
      ...current,
      newSaleBillRow(Math.max(...current.map((row) => row.rowId)) + 1),
    ]);
    window.setTimeout(() => {
      document.querySelector<HTMLElement>(
        ".consignment-panel [data-grid-row]:last-of-type input",
      )?.focus();
    }, 0);
  }

  const handleSaleGridEnter = useGridEnterNavigation(appendSaleRow);

  const documentLines = rows
    .filter((row) => row.commodity && saleBillQuantity(row) > 0 && Number(row.rate) >= 0)
    .map((row) => ({
      commodity_id: row.commodity?.id,
      source_party_id: row.commissionAgent?.id ?? null,
      source_reference_number: row.sourceNumber,
      description: row.commodity?.label ?? "Commodity",
      bags_scaled: Math.round(Number(row.bags || 0)),
      bag_scale: 0,
      packing_weight_scaled: Math.round(Number(row.pack || 0) * 1000),
      loose_quantity_scaled: Math.round(Number(row.extra || 0) * 1000),
      quantity_scaled: Math.round(saleBillQuantity(row) * 1000),
      quantity_scale: 3,
      rate_paise: rupeesToPaise(row.rate),
      rate_unit: "quintal",
    }));

  const payload = {
    document_type: type,
    document_number: number,
    document_date: date,
    party_id: party?.id ?? null,
    main_account_id: saleAccount?.id ?? null,
    party_account_id: partyAccount?.id ?? null,
    excluded_charge_codes: excludedCharges,
    overrides: buildChargeOverrides(calculation, rateOverrides),
    lines: documentLines,
    header: {
      due_date: dueDate,
      vehicle_number: vehicle,
      gr_number: grNumber,
      gr_date: grDate,
      dispatch_time: dispatchTime,
      eway_bill_number: eway,
      to_place: deliverAt,
      remarks,
      insurance_number: insurance,
      freight_paise: rupeesToPaise(freight),
      freight_direction: freightDirection,
      advance_cash_paise: rupeesToPaise(advance),
      cash_account_id: cashAccount?.id ?? null,
      packing_material_transfer: packingTransfer,
      stock_sale: stockSale,
      multi_tax: multiTax,
    },
  };

  async function calculate() {
    const response = await workflowApi()?.calculate_document(payload);
    if (response) {
      setResult(response);
      setCalculation(response.calculation ?? null);
    }
  }

  useEffect(() => {
    if (!documentLines.length) return;
    const timer = window.setTimeout(() => {
      void workflowApi()?.calculate_document(payload).then((response) => {
        if (response.ok) setCalculation(response.calculation ?? null);
      });
    }, 180);
    return () => window.clearTimeout(timer);
  }, [JSON.stringify(payload)]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!party || !partyAccount || !saleAccount || !documentLines.length) {
      setResult({
        ok: false,
        error: "Select the buyer, posting accounts and at least one complete commodity row.",
      });
      return;
    }
    if (rupeesToPaise(advance) > 0 && !cashAccount) {
      setResult({ ok: false, error: "Select a cash account for advance cash paid." });
      return;
    }
    if (eway && !/^\d{10,12}$/.test(eway)) {
      setResult({ ok: false, error: "e-Way Bill No. must contain 10 to 12 digits." });
      return;
    }
    const response = await workflowApi()?.post_document(payload);
    if (!response) return;
    setResult(response);
    const document = response.document as { document_id?: string } | undefined;
    if (response.ok && document?.document_id) {
      setPostedId(document.document_id);
      setShowSavedModal(true);
    }
  }

  async function printDocument() {
    if (!postedId) return;
    const response = await workflowApi()?.print_document(postedId);
    if (response) {
      setResult(response);
      if (response.ok) setShowSavedModal(true);
    }
  }

  const charges = (calculation?.charges ?? []) as Record<string, unknown>[];
  const expenseCharges = charges.filter((charge) => !charge.is_tax);
  const taxCharges = charges.filter((charge) => charge.is_tax);
  const totalBags = rows.reduce((sum, row) => sum + Number(row.bags || 0), 0);
  const totalExtra = rows.reduce((sum, row) => sum + Number(row.extra || 0), 0);
  const totalQuantity = rows.reduce((sum, row) => sum + saleBillQuantity(row), 0);
  const grossAmount = rows.reduce(
    (sum, row) => sum + saleBillQuantity(row) * Number(row.rate || 0),
    0,
  );
  const netPaise = Number(calculation?.grand_total_paise ?? 0);
  const balancePaise = Math.max(0, netPaise - rupeesToPaise(advance));

  return (
    <form
      ref={formRef}
      className="sale-bill-screen"
      data-grid-scope
      onKeyDown={handleSaleGridEnter}
      onSubmit={(event) => void submit(event)}
    >
      <header className="sale-bill-header">
        <div className="buyer-details">
          <Autocomplete autoFocus entityType="party" label="Party Name" required value={party} onSelect={selectParty} />
          <label>Address<textarea readOnly value={party?.address ?? ""} /></label>
          <label>GSTIN<input readOnly value={party?.gstin ?? ""} /></label>
        </div>
        <div className="invoice-metadata">
          <label>No.<input required value={number} onChange={(event) => setNumber(event.target.value)} /></label>
          <label>Date<input required type="date" value={date} onChange={(event) => setDate(event.target.value)} /></label>
          <label>Due Date<input type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} /></label>
        </div>
      </header>

      <div className="logistics-row">
        <label>Vehicle No.<input value={vehicle} onChange={(event) => setVehicle(event.target.value.toUpperCase())} /></label>
        <label>GR No.<input value={grNumber} onChange={(event) => setGrNumber(event.target.value)} /></label>
        <label>GR Date<input type="date" value={grDate} onChange={(event) => setGrDate(event.target.value)} /></label>
        <label>Time<input type="time" value={dispatchTime} onChange={(event) => setDispatchTime(event.target.value)} /></label>
        <label>e-Way Bill No.<input inputMode="numeric" value={eway} onChange={(event) => setEway(event.target.value.replace(/\D/g, ""))} /></label>
        <label>Deliver at<input value={deliverAt} onChange={(event) => setDeliverAt(event.target.value)} /></label>
      </div>

      <div className="sale-bill-content">
        <section className="consignment-panel">
          <h3>Dheri Details</h3>
          <div className="sale-line-grid sale-line-header">
            <span>Commodity</span><span>No.</span><span>Commission Agent</span>
            <span>Bags</span><span>Pack</span><span>Extra</span><span>Quantity</span>
            <span>Rate</span><span>Amount</span><span />
          </div>
          {rows.map((row) => {
            const quantity = saleBillQuantity(row);
            const amount = quantity * Number(row.rate || 0);
            return (
              <div className="sale-line-grid" data-grid-row key={row.rowId}>
                <Autocomplete entityType="commodity" label="" value={row.commodity} onSelect={(value) => updateRow(row.rowId, { commodity: value })} />
                <input value={row.sourceNumber} onChange={(event) => updateRow(row.rowId, { sourceNumber: event.target.value })} />
                <Autocomplete entityType="party" label="" value={row.commissionAgent} onSelect={(value) => updateRow(row.rowId, { commissionAgent: value })} />
                <input type="number" min="0" step="1" value={row.bags} onChange={(event) => updateRow(row.rowId, { bags: event.target.value })} />
                <input inputMode="decimal" value={row.pack} onChange={(event) => updateRow(row.rowId, { pack: event.target.value })} />
                <input inputMode="decimal" value={row.extra} onChange={(event) => updateRow(row.rowId, { extra: event.target.value })} />
                <output>{quantity.toFixed(3)}</output>
                <input inputMode="decimal" value={row.rate} onChange={(event) => updateRow(row.rowId, { rate: event.target.value })} />
                <output>{amount.toFixed(2)}</output>
                <button aria-label="Remove row" disabled={rows.length === 1} type="button" onClick={() => setRows((current) => current.filter((item) => item.rowId !== row.rowId))}>×</button>
              </div>
            );
          })}
          <button className="add-dheri" type="button" onClick={appendSaleRow}>Add Row</button>
          <div className="sale-grid-totals">
            <strong>Totals</strong><span>{totalBags.toFixed(0)} Bags</span>
            <span>{totalExtra.toFixed(3)} Extra</span><span>{totalQuantity.toFixed(3)} Qty</span>
            <span>₹{grossAmount.toFixed(2)}</span>
          </div>
        </section>

        <aside className="expense-panel sale-expenses">
          <h3>Expenses Details</h3>
          <div className="expense-list">
            <div className="expense-list-header">
              <span /><span>Expense</span><span>% / Unit</span><span>Amount</span>
            </div>
            {expenseCharges.map((charge) => (
              <label key={String(charge.code)}>
                <input type="checkbox" checked={!excludedCharges.includes(String(charge.code))} onChange={(event) => setExcludedCharges((codes) => event.target.checked ? codes.filter((code) => code !== String(charge.code)) : [...codes, String(charge.code)])} />
                <span>{String(charge.label)}</span><input aria-label={`${String(charge.label)} rate`} value={rateOverrides[String(charge.code)] ?? String(charge.rate_decimal)} onChange={(event) => setRateOverrides((current) => ({ ...current, [String(charge.code)]: event.target.value }))} />
                <strong>₹{(Number(charge.final_amount_paise) / 100).toFixed(2)}</strong>
              </label>
            ))}
            {!expenseCharges.length && <p>Configure Sale Invoice mandi charges, then select Refresh.</p>}
          </div>
          <button type="button" onClick={() => void calculate()}>Add / Remove Exp. &amp; Refresh</button>
          <div className="invoice-total-block">
            <span>Total Expenses</span><output>₹{(Number(calculation?.total_charges_paise ?? 0) / 100).toFixed(2)}</output>
            <span>Total Amount</span><output>₹{(Number(calculation?.taxable_total_paise ?? 0) / 100).toFixed(2)}</output>
            {taxCharges.map((charge) => (
              <div className="tax-total-row" key={String(charge.code)}>
                <span>{String(charge.label)} {String(charge.rate_decimal)}%</span>
                <output>₹{(Number(charge.final_amount_paise) / 100).toFixed(2)}</output>
              </div>
            ))}
            <strong>NET AMOUNT</strong><output>₹{(netPaise / 100).toFixed(2)}</output>
          </div>
        </aside>
      </div>

      <footer className="sale-bill-footer">
        <div className="payment-fields">
          <label>Freight<select value={freightDirection} onChange={(event) => setFreightDirection(event.target.value)}><option value="add">Add</option><option value="deduct">Deduct</option></select><input type="number" min="0" step="0.01" value={freight} onChange={(event) => setFreight(event.target.value)} /></label>
          <label>Advance Cash Paid<input type="number" min="0" step="0.01" value={advance} onChange={(event) => setAdvance(event.target.value)} /></label>
          <label>Balance Amount<output>₹{(balancePaise / 100).toFixed(2)}</output></label>
        </div>
        <label>Remarks / Insurance No.<textarea value={remarks} onChange={(event) => setRemarks(event.target.value)} /><input placeholder="Insurance No." value={insurance} onChange={(event) => setInsurance(event.target.value)} /></label>
        <div className="posting-accounts">
          <Autocomplete entityType="account" label="Sale Account" required value={saleAccount} onSelect={setSaleAccount} />
          <Autocomplete entityType="account" label="Party Account" required value={partyAccount} onSelect={setPartyAccount} />
          {rupeesToPaise(advance) > 0 && <Autocomplete entityType="account" label="Cash Account" required value={cashAccount} onSelect={setCashAccount} />}
        </div>
        <div className="invoice-toggles">
          <label><input type="checkbox" checked={packingTransfer} onChange={(event) => setPackingTransfer(event.target.checked)} /> Packing Material (Transfer)</label>
          <label><input type="checkbox" checked={stockSale} onChange={(event) => setStockSale(event.target.checked)} /> Stock Sale</label>
          <label><input type="checkbox" checked={multiTax} onChange={(event) => setMultiTax(event.target.checked)} /> Multi Tax</label>
        </div>
        <MandiVoucherActions
          postedId={postedId}
          onCalculate={() => void calculate()}
          onExit={onExit}
          onPrint={() => void printDocument()}
        />
      </footer>
      {!showSavedModal && <Message result={result} />}
      {showSavedModal && <SavedModal onClose={() => setShowSavedModal(false)} />}
      <input type="hidden" value={postedId} readOnly />
    </form>
  );
}

type CreditPurchaseRow = {
  rowId: number;
  commodity: LookupItem | null;
  bags: string;
  pack: string;
  extra: string;
  rate: string;
};

function newCreditPurchaseRow(rowId: number, commodity: LookupItem | null = null): CreditPurchaseRow {
  return { rowId, commodity, bags: "", pack: "50", extra: "", rate: "" };
}

function creditPurchaseQuantity(row: CreditPurchaseRow): number {
  return ((Number(row.bags || 0) * Number(row.pack || 0)) + Number(row.extra || 0)) / 100;
}

function FormICredit({ onExit }: { onExit(): void }) {
  const formRef = useRef<HTMLFormElement>(null);
  useFormEnterFlow(formRef);
  useFieldFocusHandlers(formRef);
  const [party, setParty] = useState<LookupItem | null>(null);
  const [partyAccount, setPartyAccount] = useState<LookupItem | null>(null);
  const [purchaseAccount, setPurchaseAccount] = useState<LookupItem | null>(null);
  const [formINumber, setFormINumber] = useState("");
  const [headerCommodity, setHeaderCommodity] = useState<LookupItem | null>(null);
  const [number, setNumber] = useState("");
  const [date, setDate] = useState(today());
  const [dueDate, setDueDate] = useState(today());
  const [rows, setRows] = useState<CreditPurchaseRow[]>([newCreditPurchaseRow(1)]);
  const [bonus, setBonus] = useState("");
  const [excludedCharges, setExcludedCharges] = useState<string[]>([]);
  const [rateOverrides, setRateOverrides] = useState<Record<string, string>>({});
  const [calculation, setCalculation] = useState<Record<string, unknown> | null>(null);
  const [commodityBalance, setCommodityBalance] = useState("0.000");
  const [result, setResult] = useState<Result | null>(null);
  const [showSavedModal, setShowSavedModal] = useState(false);
  const [postedId, setPostedId] = useState("");

  useEffect(() => {
    void workflowApi()?.next_document_number("form_i_credit").then((response) => {
      if (response.document_number) setNumber(response.document_number);
    });
  }, []);

  useEffect(() => {
    if (!headerCommodity) {
      setCommodityBalance("0.000");
      return;
    }
    void workflowApi()?.stock_balance().then((response) => {
      const stockRow = (response.rows ?? []).find(
        (row) => String(row.commodity_id) === headerCommodity.id,
      );
      if (!stockRow) {
        setCommodityBalance("0.000");
        return;
      }
      const scale = Number(stockRow.quantity_scale ?? 3);
      setCommodityBalance(
        (Number(stockRow.quantity_scaled ?? 0) / (10 ** scale)).toFixed(scale),
      );
    });
  }, [headerCommodity]);

  function selectParty(value: LookupItem | null) {
    setParty(value);
    if (value?.account_id && value.account_name) {
      setPartyAccount({ id: value.account_id, label: value.account_name });
    }
  }

  function selectHeaderCommodity(value: LookupItem | null) {
    setHeaderCommodity(value);
    setRows((current) =>
      current.map((row, index) =>
        index === 0 && !row.commodity ? { ...row, commodity: value } : row,
      ),
    );
  }

  function updateRow(rowId: number, values: Partial<CreditPurchaseRow>) {
    setRows((current) =>
      current.map((row) => (row.rowId === rowId ? { ...row, ...values } : row)),
    );
  }

  function appendCreditRow() {
    setRows((current) => [
      ...current,
      newCreditPurchaseRow(
        Math.max(...current.map((row) => row.rowId)) + 1,
        headerCommodity,
      ),
    ]);
    window.setTimeout(() => {
      document.querySelector<HTMLElement>(
        ".credit-dheri-panel [data-grid-row]:last-of-type input",
      )?.focus();
    }, 0);
  }

  const handleCreditGridEnter = useGridEnterNavigation(appendCreditRow);

  const documentLines = rows
    .filter((row) => row.commodity && creditPurchaseQuantity(row) > 0 && Number(row.rate) >= 0)
    .map((row) => ({
      commodity_id: row.commodity?.id,
      description: row.commodity?.label ?? "Commodity",
      bags_scaled: Math.round(Number(row.bags || 0)),
      bag_scale: 0,
      packing_weight_scaled: Math.round(Number(row.pack || 0) * 1000),
      loose_quantity_scaled: Math.round(Number(row.extra || 0) * 1000),
      quantity_scaled: Math.round(creditPurchaseQuantity(row) * 1000),
      quantity_scale: 3,
      rate_paise: rupeesToPaise(row.rate),
      rate_unit: "quintal",
    }));

  const payload = {
    document_type: "form_i_credit",
    document_number: number,
    document_date: date,
    party_id: party?.id ?? null,
    main_account_id: purchaseAccount?.id ?? null,
    party_account_id: partyAccount?.id ?? null,
    excluded_charge_codes: excludedCharges,
    overrides: buildChargeOverrides(calculation, rateOverrides),
    bonus_paise: rupeesToPaise(bonus),
    lines: documentLines,
    header: {
      reference_number: formINumber,
      due_date: dueDate,
      bonus_direction: "deduct",
    },
  };

  async function calculate() {
    const response = await workflowApi()?.calculate_document(payload);
    if (response) {
      setResult(response);
      setCalculation(response.calculation ?? null);
    }
  }

  useEffect(() => {
    if (!documentLines.length) return;
    const timer = window.setTimeout(() => {
      void workflowApi()?.calculate_document(payload).then((response) => {
        if (response.ok) setCalculation(response.calculation ?? null);
      });
    }, 180);
    return () => window.clearTimeout(timer);
  }, [JSON.stringify(payload)]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!party || !purchaseAccount || !partyAccount || !documentLines.length) {
      setResult({
        ok: false,
        error: "Select the party, posting accounts and at least one complete Dheri row.",
      });
      return;
    }
    const response = await workflowApi()?.post_document(payload);
    if (!response) return;
    setResult(response);
    if (response.ok) {
      const document = response.document as { document_id?: string } | undefined;
      if (document?.document_id) setPostedId(document.document_id);
      setShowSavedModal(true);
    }
  }

  async function printDocument() {
    if (!postedId) return;
    const response = await workflowApi()?.print_document(postedId);
    if (response) {
      setResult(response);
      if (response.ok) setShowSavedModal(true);
    }
  }

  const charges = (calculation?.charges ?? []) as Record<string, unknown>[];
  const expenses = charges.filter((charge) => !charge.is_tax && charge.code !== "BONUS");
  const taxes = charges.filter((charge) => charge.is_tax);
  const totalBags = rows.reduce((sum, row) => sum + Number(row.bags || 0), 0);
  const totalQuantity = rows.reduce((sum, row) => sum + creditPurchaseQuantity(row), 0);
  const grossAmount = rows.reduce(
    (sum, row) => sum + creditPurchaseQuantity(row) * Number(row.rate || 0),
    0,
  );

  return (
    <form
      ref={formRef}
      className="form-i-credit-screen sale-bill-screen"
      data-grid-scope
      onKeyDown={handleCreditGridEnter}
      onSubmit={(event) => void submit(event)}
    >
      <header className="credit-header sale-bill-header">
        <div className="buyer-details">
          <Autocomplete autoFocus entityType="party" label="Party Name" required value={party} onSelect={selectParty} />
          <label>
            <span>Form - I No.</span>
            <input data-enter-order={2} value={formINumber} onChange={(event) => setFormINumber(event.target.value)} />
          </label>
          <Autocomplete entityType="commodity" label="Commodity" value={headerCommodity} onSelect={selectHeaderCommodity} />
        </div>
        <div className="invoice-metadata voucher-metadata">
          <label><span>No.</span><input required data-enter-order={4} value={number} onChange={(event) => setNumber(event.target.value)} /></label>
          <label><span>Date</span><input required data-enter-order={5} type="date" value={date} onChange={(event) => setDate(event.target.value)} /></label>
          <label><span>Due Date</span><input data-enter-order={6} type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} /></label>
        </div>
      </header>

      <div className="credit-content sale-bill-content">
        <section className="credit-dheri-panel consignment-panel">
          <h3>Dheri Details</h3>
          <div className="credit-line-grid credit-line-header sale-line-header">
            <span>Commodity</span><span>Bags</span><span>Pack</span><span>Extra</span>
            <span>Quantity</span><span>Rate</span><span>Amount</span><span />
          </div>
          {rows.map((row) => {
            const quantity = creditPurchaseQuantity(row);
            return (
              <div className="credit-line-grid" data-grid-row key={row.rowId}>
                <Autocomplete entityType="commodity" label="" value={row.commodity} onSelect={(value) => updateRow(row.rowId, { commodity: value })} />
                <input type="number" min="0" step="1" value={row.bags} onChange={(event) => updateRow(row.rowId, { bags: event.target.value })} />
                <input inputMode="decimal" value={row.pack} onChange={(event) => updateRow(row.rowId, { pack: event.target.value })} />
                <input inputMode="decimal" value={row.extra} onChange={(event) => updateRow(row.rowId, { extra: event.target.value })} />
                <output>{quantity.toFixed(3)}</output>
                <input inputMode="decimal" value={row.rate} onChange={(event) => updateRow(row.rowId, { rate: event.target.value })} />
                <output>{(quantity * Number(row.rate || 0)).toFixed(2)}</output>
                <button aria-label="Remove row" disabled={rows.length === 1} type="button" onClick={() => setRows((current) => current.filter((item) => item.rowId !== row.rowId))}>×</button>
              </div>
            );
          })}
          <button className="add-dheri" type="button" onClick={appendCreditRow}>Add Row</button>
          <div className="credit-grid-footer">
            <span>Commodity Balance <output>{commodityBalance}</output></span>
            <span>{totalBags.toFixed(0)} Bags</span>
            <span>{totalQuantity.toFixed(3)} Qty</span>
            <span>₹{grossAmount.toFixed(2)}</span>
          </div>
        </section>

        <aside className="expense-panel credit-expenses sale-expenses">
          <h3>Expenses Details</h3>
          <div className="expense-list">
            <div className="expense-list-header">
              <span /><span>Expense</span><span>% / Unit</span><span>Amount</span>
            </div>
            {expenses.map((charge) => (
              <label key={String(charge.code)}>
                <input type="checkbox" checked={!excludedCharges.includes(String(charge.code))} onChange={(event) => setExcludedCharges((codes) => event.target.checked ? codes.filter((code) => code !== String(charge.code)) : [...codes, String(charge.code)])} />
                <span>{String(charge.label)}</span><input aria-label={`${String(charge.label)} rate`} value={rateOverrides[String(charge.code)] ?? String(charge.rate_decimal)} onChange={(event) => setRateOverrides((current) => ({ ...current, [String(charge.code)]: event.target.value }))} />
                <strong>₹{(Number(charge.final_amount_paise) / 100).toFixed(2)}</strong>
              </label>
            ))}
          </div>
          <button type="button" onClick={() => void calculate()}>Add / Remove Exp. &amp; Refresh</button>
          <div className="invoice-total-block">
            <span>Total Expenses</span><output>₹{(Number(calculation?.total_charges_paise ?? 0) / 100).toFixed(2)}</output>
            <span>Total Amount</span><output>₹{(Number(calculation?.taxable_total_paise ?? 0) / 100).toFixed(2)}</output>
            {taxes.map((charge) => (
              <div className="tax-total-row" key={String(charge.code)}>
                <span>{String(charge.label)}</span><output>₹{(Number(charge.final_amount_paise) / 100).toFixed(2)}</output>
              </div>
            ))}
            {!taxes.length && <><span>SGST / CGST</span><output>₹0.00</output></>}
            <label>Bonus<input type="number" min="0" step="0.01" value={bonus} onChange={(event) => setBonus(event.target.value)} /></label>
            <strong>NET AMOUNT</strong><output>₹{(Number(calculation?.grand_total_paise ?? 0) / 100).toFixed(2)}</output>
          </div>
        </aside>
      </div>

      <footer className="credit-footer sale-bill-footer">
        <div className="posting-accounts">
          <Autocomplete entityType="account" label="Purchase Account" required value={purchaseAccount} onSelect={setPurchaseAccount} />
          <Autocomplete entityType="account" label="Party Account" required value={partyAccount} onSelect={setPartyAccount} />
        </div>
        <MandiVoucherActions
          postedId={postedId}
          onCalculate={() => void calculate()}
          onExit={onExit}
          onPrint={() => void printDocument()}
        />
      </footer>
      {!showSavedModal && <Message result={result} />}
      {showSavedModal && <SavedModal onClose={() => setShowSavedModal(false)} />}
    </form>
  );
}

function DocumentForm({ title, onExit }: { title: string; onExit(): void }) {
  const type = documentTypes[title] ?? "sale_invoice";
  const financial = type !== "transfer_challan";
  const [number, setNumber] = useState("");
  const [date, setDate] = useState(today());
  const [party, setParty] = useState<LookupItem | null>(null);
  const [commodity, setCommodity] = useState<LookupItem | null>(null);
  const [mainAccount, setMainAccount] = useState<LookupItem | null>(null);
  const [partyAccount, setPartyAccount] = useState<LookupItem | null>(null);
  const [bags, setBags] = useState("");
  const [quantity, setQuantity] = useState("");
  const [rate, setRate] = useState("");
  const [vehicle, setVehicle] = useState("");
  const [eway, setEway] = useState("");
  const [calculation, setCalculation] = useState<Record<string, unknown> | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [postedId, setPostedId] = useState("");
  const [pdfPath, setPdfPath] = useState("C:\\AnajERP\\invoice.pdf");
  const [showSavedModal, setShowSavedModal] = useState(false);

  const payload = {
    document_type: type,
    document_number: number,
    document_date: date,
    party_id: party?.id ?? null,
    main_account_id: mainAccount?.id ?? null,
    party_account_id: partyAccount?.id ?? null,
    lines: commodity ? [{
      commodity_id: commodity.id,
      description: commodity.label,
      bags_scaled: Math.round(Number(bags || 0)),
      bag_scale: 0,
      quantity_scaled: Math.round(Number(quantity || 0) * 1000),
      quantity_scale: 3,
      rate_paise: rupeesToPaise(rate),
      rate_unit: "quintal",
    }] : [],
    header: {
      vehicle_number: vehicle,
      eway_bill_number: eway,
    },
  };

  async function preview() {
    const response = await workflowApi()?.calculate_document(payload);
    if (response) {
      setResult(response);
      setCalculation(response.calculation ?? null);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!party || !commodity || (financial && (!mainAccount || !partyAccount))) {
      setResult({ ok: false, error: "Select the required masters and accounts." });
      return;
    }
    const response = await workflowApi()?.post_document(payload);
    if (response) {
      setResult(response);
      const document = response.document as { document_id?: string } | undefined;
      if (document?.document_id) setPostedId(document.document_id);
      if (response.ok) setShowSavedModal(true);
    }
  }

  async function createPdf() {
    if (!postedId) return;
    const response = await workflowApi()?.create_invoice_pdf(postedId, pdfPath, "original");
    if (response) setResult(response);
  }

  async function printDocument() {
    if (!postedId) return;
    const response = await workflowApi()?.print_document(postedId);
    if (response) {
      setResult(response);
      if (response.ok) setShowSavedModal(true);
    }
  }

  return (
    <form className="entry-form document-form" onKeyDown={moveToNextField} onSubmit={(e) => void submit(e)}>
      <label>No.<input autoFocus required value={number} onChange={(e) => setNumber(e.target.value)} /></label>
      <label>Date<input required type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label>
      <Autocomplete entityType="party" label="Party / Farmer" required value={party} onSelect={setParty} />
      <Autocomplete entityType="commodity" label="Commodity" required value={commodity} onSelect={setCommodity} />
      {financial && <Autocomplete entityType="account" label="Purchase / Sale Account" required value={mainAccount} onSelect={setMainAccount} />}
      {financial && <Autocomplete entityType="account" label="Party Account" required value={partyAccount} onSelect={setPartyAccount} />}
      <label>Bags<input min="0" step="1" type="number" value={bags} onChange={(e) => setBags(e.target.value)} /></label>
      <label>Quantity / Weight<input required min="0.001" step="0.001" type="number" value={quantity} onChange={(e) => setQuantity(e.target.value)} /></label>
      <label>Rate (Rs.)<input required min="0" step="0.01" type="number" value={rate} onChange={(e) => setRate(e.target.value)} /></label>
      <label>Vehicle No.<input value={vehicle} onChange={(e) => setVehicle(e.target.value)} /></label>
      <label>e-Way Bill<input value={eway} onChange={(e) => setEway(e.target.value)} /></label>
      <div className="form-actions">
        <button type="button" onClick={() => void preview()}>Calculate</button>
        <button disabled={!postedId} type="button" onClick={() => void printDocument()}>Print</button>
        <button type="submit">Save</button>
        <button type="button" onClick={onExit}>Exit</button>
      </div>
      {calculation && (
        <div className="calculation-summary">
          <strong>Calculated Total</strong>
          <span>Value: ₹{(Number(calculation.subtotal_paise) / 100).toFixed(2)}</span>
          <span>Charges: ₹{(Number(calculation.total_charges_paise) / 100).toFixed(2)}</span>
          <span>Tax: ₹{(Number(calculation.total_tax_paise) / 100).toFixed(2)}</span>
          <span>Net: ₹{(Number(calculation.grand_total_paise) / 100).toFixed(2)}</span>
        </div>
      )}
      {postedId && (
        <div className="print-row">
          <input aria-label="PDF destination" value={pdfPath} onChange={(e) => setPdfPath(e.target.value)} />
          <button type="button" onClick={() => void createPdf()}>Save PDF</button>
        </div>
      )}
      {!showSavedModal && <Message result={result} />}
      {showSavedModal && <SavedModal onClose={() => setShowSavedModal(false)} />}
    </form>
  );
}

function ReportView({ kind }: { kind: "trial" | "stock" }) {
  const [result, setResult] = useState<Result | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    const api = workflowApi();
    if (!api) return;
    const request = kind === "trial" ? api.trial_balance() : api.stock_balance();
    void request.then(setResult);
  }, [kind]);

  const rows = result?.rows ?? [];
  const columns = rows.length ? Object.keys(rows[0]) : [];
  const filteredRows = useMemo(
    () => rows.filter((row) => fuzzyMatch(query, columns.map((column) => String(row[column] ?? "")).join(" "))),
    [rows, columns, query],
  );
  return (
    <section className="flex h-full min-h-0 flex-col overflow-hidden p-2">
      <div className="mb-2 flex items-center gap-2">
        <h2 className="text-sm font-semibold">{kind === "trial" ? "Trial Balance" : "Commodity Balance"}</h2>
        <input
          className="ml-auto w-64 rounded border px-2 py-1 text-xs"
          placeholder="Search..."
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>
      <Message result={result} />
      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-full border-collapse text-xs">
          <thead><tr>{columns.map((column) => <th className="border px-1 py-0.5 text-left" key={column}>{column.replaceAll("_", " ")}</th>)}</tr></thead>
          <tbody>{filteredRows.map((row, index) => (
            <tr className="transition-opacity" key={index}>{columns.map((column) => <td className="border px-1 py-0.5" key={column}>{String(row[column] ?? "")}</td>)}</tr>
          ))}</tbody>
        </table>
      </div>
    </section>
  );
}

function TaxRegister({ family }: { family: "GST" | "TDS" | "MANDI" }) {
  const [from, setFrom] = useState(`${new Date().getFullYear()}-04-01`);
  const [to, setTo] = useState(today());
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<Result | null>(null);

  async function load(event: FormEvent) {
    event.preventDefault();
    const response = await workflowApi()?.tax_register(from, to, family);
    if (response) setResult(response);
  }

  const rows = result?.rows ?? [];
  const columns = rows.length ? Object.keys(rows[0]) : [];
  const filteredRows = useMemo(
    () => rows.filter((row) => fuzzyMatch(query, columns.map((column) => String(row[column] ?? "")).join(" "))),
    [rows, columns, query],
  );
  return (
    <section className="flex h-full min-h-0 flex-col overflow-hidden p-2">
      <h2 className="mb-2 text-sm font-semibold">{family === "MANDI" ? "Mandi / HRDF Register" : `${family} Register`}</h2>
      <form className="mb-2 flex flex-wrap items-end gap-2 text-xs" onSubmit={(event) => void load(event)}>
        <label>From<input className="rounded border px-1 py-0.5" type="date" value={from} onChange={(event) => setFrom(event.target.value)} /></label>
        <label>To<input className="rounded border px-1 py-0.5" type="date" value={to} onChange={(event) => setTo(event.target.value)} /></label>
        <input className="rounded border px-2 py-0.5" placeholder="Search..." value={query} onChange={(event) => setQuery(event.target.value)} />
        <button type="submit">Refresh</button>
      </form>
      <Message result={result} />
      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-full border-collapse text-xs">
          <thead><tr>{columns.map((column) => <th className="border px-1 py-0.5 text-left" key={column}>{column.replaceAll("_", " ")}</th>)}</tr></thead>
          <tbody>{filteredRows.map((row, index) => (
            <tr className="transition-opacity" key={index}>{columns.map((column) => <td className="border px-1 py-0.5" key={column}>{String(row[column] ?? "")}</td>)}</tr>
          ))}</tbody>
        </table>
      </div>
    </section>
  );
}

function ChargeRuleForm() {
  const [code, setCode] = useState("COMMISSION");
  const [label, setLabel] = useState("Commission");
  const [transactionType, setTransactionType] = useState("sale_invoice");
  const [basis, setBasis] = useState("amount");
  const [mode, setMode] = useState("percentage");
  const [rate, setRate] = useState("1.00");
  const [direction, setDirection] = useState("add");
  const [isTax, setIsTax] = useState(false);
  const [effectiveFrom, setEffectiveFrom] = useState(today());
  const [ledger, setLedger] = useState<LookupItem | null>(null);
  const [result, setResult] = useState<Result | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const response = await workflowApi()?.create_charge_rule({
      code,
      label,
      transaction_type: transactionType,
      basis,
      mode,
      rate_decimal: rate,
      direction,
      is_tax: isTax,
      effective_from: effectiveFrom,
      ledger_account_id: ledger?.id ?? null,
    });
    if (response) setResult(response);
  }

  return (
    <form className="entry-form charge-rule-form" onKeyDown={moveToNextField} onSubmit={(event) => void submit(event)}>
      <h2>Tax &amp; Charge Rule</h2>
      <label>Code<input value={code} onChange={(event) => setCode(event.target.value.toUpperCase())} /></label>
      <label>Print Label<input value={label} onChange={(event) => setLabel(event.target.value)} /></label>
      <label>Transaction<select value={transactionType} onChange={(event) => setTransactionType(event.target.value)}>
        {Object.entries(documentTypes).map(([display, value]) => <option key={value} value={value}>{display}</option>)}
      </select></label>
      <label>Basis<select value={basis} onChange={(event) => setBasis(event.target.value)}>
        {["amount", "bag", "quantity", "weight"].map((value) => <option key={value}>{value}</option>)}
      </select></label>
      <label>Mode<select value={mode} onChange={(event) => setMode(event.target.value)}>
        <option value="percentage">Percentage</option><option value="fixed">Fixed per unit</option>
      </select></label>
      <label>Rate<input type="number" min="0" step="0.0001" value={rate} onChange={(event) => setRate(event.target.value)} /></label>
      <label>Direction<select value={direction} onChange={(event) => setDirection(event.target.value)}>
        <option value="add">Add</option><option value="deduct">Deduct</option>
      </select></label>
      <label>Effective From<input type="date" value={effectiveFrom} onChange={(event) => setEffectiveFrom(event.target.value)} /></label>
      <Autocomplete entityType="account" label="Posting Ledger" value={ledger} onSelect={setLedger} />
      <label className="checkbox-label"><input type="checkbox" checked={isTax} onChange={(event) => setIsTax(event.target.checked)} /> GST / Tax Rule</label>
      <button type="submit">Save Rule</button>
      <Message result={result} />
    </form>
  );
}

function InterestForm() {
  const [account, setAccount] = useState<LookupItem | null>(null);
  const [from, setFrom] = useState(`${new Date().getFullYear()}-04-01`);
  const [to, setTo] = useState(today());
  const [rate, setRate] = useState("18.00");
  const [result, setResult] = useState<Result | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!account) {
      setResult({ ok: false, error: "Select an account." });
      return;
    }
    const response = await workflowApi()?.calculate_interest(
      account.id,
      from,
      to,
      rate,
    );
    if (response) setResult(response);
  }

  return (
    <form className="entry-form" onSubmit={(event) => void submit(event)}>
      <h2>Interest Calculation</h2>
      <Autocomplete entityType="account" label="Account" value={account} onSelect={setAccount} />
      <label>From<input type="date" value={from} onChange={(event) => setFrom(event.target.value)} /></label>
      <label>To<input type="date" value={to} onChange={(event) => setTo(event.target.value)} /></label>
      <label>Annual Rate %<input type="number" step="0.01" value={rate} onChange={(event) => setRate(event.target.value)} /></label>
      <button type="submit">Calculate</button>
      {result?.interest && (
        <div className="calculation-summary">
          <span>Principal: ₹{(Number(result.interest.principal_paise) / 100).toFixed(2)}</span>
          <span>Days: {String(result.interest.days)}</span>
          <strong>Interest: ₹{(Number(result.interest.interest_paise) / 100).toFixed(2)}</strong>
        </div>
      )}
      <Message result={result} />
    </form>
  );
}

function Configuration() {
  const [path, setPath] = useState("C:\\AnajERP\\backup");
  const [result, setResult] = useState<Result | null>(null);

  async function run(action: "create_backup" | "restore_new_company") {
    const api = workflowApi();
    if (!api) return;
    const response = await api[action](path);
    setResult(response);
  }

  async function reconcile() {
    const response = await workflowApi()?.reconcile_company();
    if (response) setResult(response);
  }

  async function migration(dryRun: boolean) {
    const response = await workflowApi()?.import_master_csv("party", path, dryRun);
    if (response) setResult(response);
  }

  return (
    <section className="entry-form configuration-form">
      <h2>Administration / Backup</h2>
      <p className="status-message">
        Anaj ERP is a standalone single-user local application. Pakki and Dasti must remain separate companies with isolated databases.
      </p>
      <label>File / Folder Path<input value={path} onChange={(e) => setPath(e.target.value)} /></label>
      <div className="configuration-actions">
        <button type="button" onClick={() => void run("create_backup")}>Create Backup</button>
        <button type="button" onClick={() => void run("restore_new_company")}>Restore New Company</button>
        <button type="button" onClick={() => void migration(true)}>Check Party CSV</button>
        <button type="button" onClick={() => void migration(false)}>Import Party CSV</button>
        <button type="button" onClick={() => void reconcile()}>Run Reconciliation</button>
      </div>
      <Message result={result} />
      {result?.reconciliation && <pre>{JSON.stringify(result.reconciliation, null, 2)}</pre>}
      {result?.migration && <pre>{JSON.stringify(result.migration, null, 2)}</pre>}
      <ChargeRuleForm />
    </section>
  );
}

function EntryWindow({
  title,
  onExit,
  readOnly = false,
}: {
  title: string;
  onExit(): void;
  readOnly?: boolean;
}) {
  const readOnlyBanner = readOnly ? (
    <p className="accounts-entry-status">Read-only access — you cannot save changes on this screen.</p>
  ) : null;
  const { screen, mode } = resolveWindowTitle(title);
  if (screen === "__accounting_reports__") {
    return (
      <section className="entry-form">
        <h2>Accounting Reports</h2>
        <p className="status-message">Open Reports → Accounting Reports and pick Cashbook, Ledger, Trial Balance, etc.</p>
      </section>
    );
  }
  if (screen === "Kachi Purchase Final") {
    return (
      <section className="entry-form">
        <h2>Kachi Purchase Final</h2>
        <p className="status-message">Finalization workflow will post closing entries from selected open Kachi bills.</p>
      </section>
    );
  }
  if (title === "New Ledger") return <LedgerForm />;
  if (title === "New Commodity") return <CommodityForm />;
  if (title === "New Party") return <PartyForm />;
  if (screen === "Cash Book") return <CashBookForm onExit={onExit} />;
  if (screen === "Voucher Entry") {
    return <VoucherEntryScreen mode={mode === "modify" ? "modify" : "add"} onExit={onExit} />;
  }
  if (screen === "TDS Challan Entry") {
    return <TdsChallanEntryScreen mode={mode === "modify" ? "modify" : "add"} onExit={onExit} />;
  }
  if (screen === "Bank Reconciliation") {
    return <BankReconciliationScreen onExit={onExit} />;
  }
  if (screen === "Find Account") {
    return <FindAccountScreen onExit={onExit} />;
  }
  if (screen === "Depreciation Chart") {
    return <DepreciationChartScreen onExit={onExit} />;
  }
  if (screen === "Stock Adjustment") {
    return <StockAdjustmentScreen mode={mode === "modify" ? "modify" : "add"} onExit={onExit} />;
  }
  if (screen === "Company Letter Head Print") {
    return <LetterHeadPrintScreen onExit={onExit} />;
  }
  if (screen === "Debit Note") {
    return <DebitNoteEntryScreen mode={mode === "modify" ? "modify" : "add"} onExit={onExit} />;
  }
  if (screen === "Credit Note") {
    return <CreditNoteEntryScreen mode={mode === "modify" ? "modify" : "add"} onExit={onExit} />;
  }
  if (["Journal", "Accounting Voucher"].includes(screen)) {
    return <JournalForm kind={screen} onExit={onExit} />;
  }
  if (screen === "Form - J") return <FormJEntryScreen onExit={onExit} />;
  if (screen === "Account Master") {
    return <AccountMasterScreen mode={mode === "modify" ? "modify" : "add"} onExit={onExit} />;
  }
  if (screen === "Standard Narration Master") {
    return <NarrationMasterScreen mode={mode === "modify" ? "modify" : "add"} onExit={onExit} />;
  }
  if (screen === "City Master") {
    return <CityMasterScreen mode={mode === "modify" ? "modify" : "add"} onExit={onExit} />;
  }
  if (screen === "Transport Master") {
    return (
      <TransportMasterScreen mode={mode === "modify" ? "modify" : "add"} onExit={onExit} />
    );
  }
  if (screen === "Trading Master") {
    return (
      <TradingAccountScreen mode={mode === "modify" ? "modify" : "add"} onExit={onExit} />
    );
  }
  if (screen === "Expenses Master Define") {
    return <ExpenseMasterScreen onExit={onExit} />;
  }
  if (screen === "I Form Expenses define") {
    return <IFormExpenseScreen onExit={onExit} />;
  }
  if (screen === "Item Entry") {
    return <ItemEntryScreen mode={mode === "modify" ? "modify" : "add"} onExit={onExit} />;
  }
  if (screen === "Cheque Print Setting") {
    return <ChequePrintSettingScreen onExit={onExit} />;
  }
  if (screen === "Bank Master") {
    return <BankMasterScreen mode={mode === "modify" ? "modify" : "add"} onExit={onExit} />;
  }
  if (screen === "IFSC Code Master") {
    return <IfscMasterScreen mode={mode === "modify" ? "modify" : "add"} onExit={onExit} />;
  }
  if (screen === "Stock Entry Master") {
    return <StockEntryScreen mode={mode === "modify" ? "modify" : "add"} onExit={onExit} />;
  }
  if (isMasterWindow(title)) {
    return <MasterForms onExit={onExit} title={screen} mode={mode} />;
  }
  if (screen === "Sale Invoice" || screen === "Form - I (Dr.)") {
    return <SaleBill title={screen} onExit={onExit} />;
  }
  if (screen === "Form - I (Cr.)") return <FormICredit onExit={onExit} />;
  if (screen === "Gst Rates" && workflowApi()) {
    return (
      <GstRatesScreen
        api={workflowApi() as never}
        mode={mode === "modify" ? "modify" : "add"}
        onExit={onExit}
      />
    );
  }
  if (title === "Fast Kachi Purchase") {
    return <KachiPurchaseScreen mode="add" onExit={onExit} />;
  }
  if (screen === "Kachi Purchase") {
    return <KachiPurchaseScreen mode={mode === "modify" ? "modify" : "add"} onExit={onExit} />;
  }
  if (screen === "Mandi Purchase Entry") {
    return <MandiPurchaseEntryScreen mode={mode === "modify" ? "modify" : "add"} onExit={onExit} />;
  }
  if (screen === "GST Purchase Entry") {
    return <GstPurchaseEntryScreen mode={mode === "modify" ? "modify" : "add"} onExit={onExit} />;
  }
  if (screen === "Invoice") {
    return <InvoiceEntryScreen mode={mode === "modify" ? "modify" : "add"} onExit={onExit} />;
  }
  if (screen === "GST Debit Note") {
    return <GstDebitNoteEntryScreen mode={mode === "modify" ? "modify" : "add"} onExit={onExit} />;
  }
  if (screen === "GST Credit Note") {
    return <GstCreditNoteEntryScreen mode={mode === "modify" ? "modify" : "add"} onExit={onExit} />;
  }
  if (screen === "GST Expense Voucher") {
    return <GstExpenseVoucherEntryScreen mode={mode === "modify" ? "modify" : "add"} onExit={onExit} />;
  }
  if (title === "Fast Lifting Entry") {
    return <LiftingEntryScreen mode="add" onExit={onExit} />;
  }
  if (screen === "Lifting Entry") {
    return <LiftingEntryScreen mode={mode === "modify" ? "modify" : "add"} onExit={onExit} />;
  }
  if (supportsDenseDocument(screen)) {
    return (
      <DenseDocumentForm
        title={screen}
        onExit={onExit}
        fastEntry={false}
        entryMode={mode}
      />
    );
  }
  if (isCompetitiveTool(screen) && workflowApi()) {
    return <CompetitiveToolRouter title={screen} api={workflowApi() as never} />;
  }
  if (isIntegrationScreen(screen) && workflowApi()) {
    return <IntegrationScreenRouter title={screen} api={workflowApi() as never} />;
  }
  if (screen in documentTypes || screen === "Sale Invoice" || screen === "Purchase Invoice") {
    return <DocumentForm title={screen} onExit={onExit} />;
  }
  if (screen === "Account Balance") return <ReportView kind="trial" />;
  if (screen === "TDS Register") return <TaxRegister family="TDS" />;
  if (screen === "Mandi Register") return <TaxRegister family="MANDI" />;
  if (isGstReportMenuTitle(title) && workflowApi()) {
    return (
      <GstReportScreen
        menuTitle={title}
        screen={screen}
        onExit={onExit}
        api={workflowApi() as never}
      />
    );
  }
  if (isCatalogReport(title, screen) && workflowApi()) {
    return (
      <LegacyReportScreen
        menuTitle={title}
        screen={screen}
        onExit={onExit}
        api={workflowApi() as never}
      />
    );
  }
  if (screen === "GST Register") return <TaxRegister family="GST" />;
  if (isToolsScreen(screen) && workflowApi()) {
    return <ToolsScreenRouter title={screen} api={workflowApi() as never} />;
  }
  if (title === "Office Users" && workflowApi()) {
    return <UserAccessScreen api={workflowApi() as never} />;
  }
  if (title === "Configuration") return <Configuration />;
  if (title === "Farmer Credit Dashboard" && window.pywebview?.api) {
    return <FarmerCreditDashboard api={window.pywebview.api as never} />;
  }
  return (
    <section className="entry-form">
      <h2>{title}</h2>
      <p>This screen is on the parity menu; detailed layout will match the reference ERP in a future batch.</p>
    </section>
  );
}

export default EntryWindow;
