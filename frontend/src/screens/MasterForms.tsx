import { FormEvent, useEffect, useState } from "react";

import Autocomplete, { LookupItem } from "../Autocomplete";
import MessageDialog from "../components/MessageDialog";
import TransactionScreen, { InlineField } from "../components/TransactionScreen";

type ApiResult = { ok: boolean; error?: string };

type MasterApi = {
  lookup_gstin?(gstin: string): Promise<ApiResult & { taxpayer?: Record<string, string> }>;
  get_party_master?(partyId: string): Promise<ApiResult & { party?: Record<string, unknown> }>;
  list_cities?(): Promise<ApiResult & { cities?: Record<string, unknown>[] }>;
  save_city?(payload: Record<string, unknown>): Promise<ApiResult>;
  list_transports?(): Promise<ApiResult & { transports?: Record<string, unknown>[] }>;
  save_transport?(payload: Record<string, unknown>): Promise<ApiResult>;
  list_narrations?(): Promise<ApiResult & { narrations?: Record<string, unknown>[] }>;
  save_narration?(payload: Record<string, unknown>): Promise<ApiResult>;
  list_banks?(): Promise<ApiResult & { banks?: Record<string, unknown>[] }>;
  save_bank?(payload: Record<string, unknown>): Promise<ApiResult>;
  list_ifsc_codes?(): Promise<ApiResult & { ifsc_codes?: Record<string, unknown>[] }>;
  save_ifsc_code?(payload: Record<string, unknown>): Promise<ApiResult>;
  save_item_master?(payload: Record<string, unknown>): Promise<ApiResult>;
  save_account_master?(payload: Record<string, unknown>): Promise<ApiResult>;
  save_expense_master?(payload: Record<string, unknown>): Promise<ApiResult>;
  save_opening_stock?(payload: Record<string, unknown>): Promise<ApiResult>;
};

function api(): MasterApi | undefined {
  return window.pywebview?.api as unknown as MasterApi | undefined;
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  enterOrder,
}: {
  label: string;
  value: string;
  onChange(value: string): void;
  type?: string;
  enterOrder?: number;
}) {
  return (
    <InlineField label={label}>
      <input
        className="w-full rounded border px-1 py-0.5"
        data-enter-order={enterOrder}
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </InlineField>
  );
}

function MasterForms({
  title,
  onExit,
  mode,
}: {
  title: string;
  onExit(): void;
  mode?: "add" | "modify";
}) {
  const [message, setMessage] = useState("");
  const [success, setSuccess] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({});
  const [commodity, setCommodity] = useState<LookupItem | null>(null);
  const [expenseLines, setExpenseLines] = useState("");
  const [modifyParty, setModifyParty] = useState<LookupItem | null>(null);
  const [gstBusy, setGstBusy] = useState(false);

  useEffect(() => {
    setForm({});
    setCommodity(null);
    setExpenseLines("");
    setModifyParty(null);
  }, [title, mode]);

  useEffect(() => {
    if (mode !== "modify" || !modifyParty?.id) return;
    void api()?.get_party_master?.(modifyParty.id).then((response) => {
      if (!response?.ok || !response.party) return;
      const party = response.party;
      setForm({
        name: String(party.name ?? ""),
        short_name: String(party.short_name ?? ""),
        print_name: String(party.print_name ?? ""),
        group_name: String(party.group_name ?? ""),
        party_type: String(party.party_type ?? "farmer"),
        gstin: String(party.gstin ?? ""),
        pan: String(party.pan ?? ""),
        address: String(party.address ?? ""),
        city: String(party.city ?? ""),
        mobile1: String(party.phone ?? ""),
        father_name: String(party.father_name ?? ""),
        opening_balance: String(party.opening_balance ?? ""),
        opening_side: String(party.opening_side ?? "Dr"),
        account_id: String(party.account_id ?? ""),
      });
    });
  }, [mode, modifyParty?.id]);

  function set(key: string, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    const bridge = api();
    if (!bridge) {
      setMessage("Desktop API is not available.");
      return;
    }
    let response: ApiResult | undefined;
    if (title === "City Master") {
      response = await bridge.save_city?.({
        name: form.name,
        state_name: form.state_name,
        state_code: form.state_code,
        district_name: form.district_name,
        pincode: form.pincode,
      });
    } else if (title === "Transport Master") {
      response = await bridge.save_transport?.({
        name: form.name,
        gstin: form.gstin,
        vehicle_details: form.vehicle_details,
        address: form.address,
        phone: form.phone,
        contact_person: form.contact_person,
      });
    } else if (title === "Standard Narration Master") {
      response = await bridge.save_narration?.({
        narration_text: form.narration_text,
        short_code: form.short_code,
      });
    } else if (title === "Bank Master") {
      response = await bridge.save_bank?.({
        name: form.name,
        account_number: form.account_number,
        ifsc_code: form.ifsc_code,
        branch_address: form.branch_address,
        opening_balance_paise: Math.round(Number(form.opening_balance || 0) * 100),
        balance_side: form.balance_side || "Dr",
      });
    } else if (title === "IFSC Code Master") {
      response = await bridge.save_ifsc_code?.({
        bank_name: form.bank_name,
        branch_name: form.branch_name,
        ifsc_code: form.ifsc_code,
        micr_code: form.micr_code,
        city: form.city,
        state: form.state,
        address: form.address,
      });
    } else if (title === "Item Entry") {
      response = await bridge.save_item_master?.({
        name: form.name,
        variety: form.variety,
        hsn_code: form.hsn_code,
        item_group: form.item_group,
        unit: form.unit,
        market_pct: form.market_pct,
        rdf_fee_pct: form.rdf_fee_pct,
        gst_type: form.gst_type,
      });
    } else if (title === "Account Master") {
      response = await bridge.save_account_master?.({
        account_id: mode === "modify" ? (form.account_id || modifyParty?.account_id) : undefined,
        name: form.name,
        account_type: form.account_type || "party",
        party_type: form.party_type || "farmer",
        short_name: form.short_name,
        print_name: form.print_name,
        group_name: form.group_name,
        gst_type: form.gst_type,
        gstin: form.gstin,
        pan: form.pan,
        address: form.address,
        city: form.city,
        mobile1: form.mobile1,
        father_name: form.father_name,
        opening_debit_paise: form.opening_side === "Dr"
          ? Math.round(Number(form.opening_balance || 0) * 100)
          : 0,
        opening_credit_paise: form.opening_side === "Cr"
          ? Math.round(Number(form.opening_balance || 0) * 100)
          : 0,
      });
    } else if (title === "Expenses Master Define") {
      let lines: unknown[] = [];
      try {
        lines = expenseLines.trim() ? JSON.parse(expenseLines) : [];
      } catch {
        setMessage("Expense lines must be valid JSON array.");
        return;
      }
      response = await bridge.save_expense_master?.({
        name: form.name,
        mandi_name: form.mandi_name,
        lines,
      });
    } else if (title === "Stock Entry Master") {
      if (!commodity) {
        setMessage("Select an item for opening stock.");
        return;
      }
      response = await bridge.save_opening_stock?.({
        commodity_id: commodity.id,
        unit: form.unit,
        bags: Number(form.bags || 0),
        quantity_scaled: Math.round(Number(form.quantity || 0) * 1000),
        rate_paise: Math.round(Number(form.rate || 0) * 100),
        amount_paise: Math.round(Number(form.amount || 0) * 100),
      });
    } else {
      setMessage("This master screen is not configured yet.");
      return;
    }
    if (!response?.ok) {
      setMessage(response?.error ?? "Save failed.");
      return;
    }
    setSuccess(true);
  }

  async function fetchGst() {
    const gstin = (form.gstin ?? "").trim();
    if (gstin.length !== 15) {
      setMessage("Enter a 15-character GSTIN first.");
      return;
    }
    setGstBusy(true);
    const response = await api()?.lookup_gstin?.(gstin);
    setGstBusy(false);
    if (!response?.ok || !response.taxpayer) {
      setMessage(response?.error ?? "GST lookup failed.");
      return;
    }
    const taxpayer = response.taxpayer;
    setForm((current) => ({
      ...current,
      name: taxpayer.trade_name || taxpayer.legal_name || current.name,
      print_name: taxpayer.legal_name || taxpayer.trade_name || current.print_name,
      gstin: taxpayer.gstin || current.gstin,
      pan: taxpayer.pan || current.pan,
      address: taxpayer.address || current.address,
      city: taxpayer.city || current.city,
      gst_status: taxpayer.status || current.gst_status,
    }));
    setMessage(taxpayer.status ? `GST status: ${taxpayer.status}` : "");
  }

  const screenTitle = mode ? `${title} ${mode === "add" ? "Add" : "Modify"}` : title;

  const fields = (() => {
    if (title === "Cheque Print Setting") {
      return <p>Cheque layout settings are configured under Tools → Prefix Settings and register print.</p>;
    }
    switch (title) {
      case "City Master":
        return (
          <>
            <Field enterOrder={1} label="City Name" value={form.name ?? ""} onChange={(v) => set("name", v)} />
            <Field enterOrder={2} label="State Name" value={form.state_name ?? ""} onChange={(v) => set("state_name", v)} />
            <Field enterOrder={3} label="State Code" value={form.state_code ?? ""} onChange={(v) => set("state_code", v)} />
            <Field enterOrder={4} label="District" value={form.district_name ?? ""} onChange={(v) => set("district_name", v)} />
            <Field enterOrder={5} label="Pincode" value={form.pincode ?? ""} onChange={(v) => set("pincode", v)} />
          </>
        );
      case "Transport Master":
        return (
          <>
            <Field enterOrder={1} label="Transport Name" value={form.name ?? ""} onChange={(v) => set("name", v)} />
            <InlineField label="GST No.">
              <div className="flex gap-1">
                <input
                  className="w-full rounded border px-1 py-0.5"
                  data-enter-order={2}
                  maxLength={15}
                  value={form.gstin ?? ""}
                  onChange={(event) => set("gstin", event.target.value.toUpperCase())}
                />
                <button disabled={gstBusy} type="button" onClick={() => void fetchGst()}>
                  {gstBusy ? "…" : "Fetch"}
                </button>
              </div>
            </InlineField>
            <Field enterOrder={3} label="Vehicle Details" value={form.vehicle_details ?? ""} onChange={(v) => set("vehicle_details", v)} />
            <Field enterOrder={4} label="Address" value={form.address ?? ""} onChange={(v) => set("address", v)} />
            <Field enterOrder={5} label="Phone" value={form.phone ?? ""} onChange={(v) => set("phone", v)} />
            <Field enterOrder={6} label="Contact Person" value={form.contact_person ?? ""} onChange={(v) => set("contact_person", v)} />
          </>
        );
      case "Standard Narration Master":
        return (
          <>
            <Field enterOrder={1} label="Narration Text" value={form.narration_text ?? ""} onChange={(v) => set("narration_text", v)} />
            <Field enterOrder={2} label="Short Code" value={form.short_code ?? ""} onChange={(v) => set("short_code", v)} />
          </>
        );
      case "Bank Master":
        return (
          <>
            <Field enterOrder={1} label="Bank Name" value={form.name ?? ""} onChange={(v) => set("name", v)} />
            <Field enterOrder={2} label="Account No." value={form.account_number ?? ""} onChange={(v) => set("account_number", v)} />
            <Field enterOrder={3} label="IFSC" value={form.ifsc_code ?? ""} onChange={(v) => set("ifsc_code", v)} />
            <Field enterOrder={4} label="Branch Address" value={form.branch_address ?? ""} onChange={(v) => set("branch_address", v)} />
            <Field enterOrder={5} label="Opening Balance" value={form.opening_balance ?? ""} onChange={(v) => set("opening_balance", v)} />
            <InlineField label="Dr/Cr">
              <select className="w-full rounded border px-1 py-0.5" data-enter-order={6} value={form.balance_side ?? "Dr"} onChange={(e) => set("balance_side", e.target.value)}>
                <option value="Dr">Dr</option>
                <option value="Cr">Cr</option>
              </select>
            </InlineField>
          </>
        );
      case "IFSC Code Master":
        return (
          <>
            <Field enterOrder={1} label="Bank Name" value={form.bank_name ?? ""} onChange={(v) => set("bank_name", v)} />
            <Field enterOrder={2} label="Branch Name" value={form.branch_name ?? ""} onChange={(v) => set("branch_name", v)} />
            <Field enterOrder={3} label="IFSC Code" value={form.ifsc_code ?? ""} onChange={(v) => set("ifsc_code", v)} />
            <Field enterOrder={4} label="MICR" value={form.micr_code ?? ""} onChange={(v) => set("micr_code", v)} />
            <Field enterOrder={5} label="City" value={form.city ?? ""} onChange={(v) => set("city", v)} />
            <Field enterOrder={6} label="State" value={form.state ?? ""} onChange={(v) => set("state", v)} />
          </>
        );
      case "Item Entry":
        return (
          <>
            <Field enterOrder={1} label="Item Name" value={form.name ?? ""} onChange={(v) => set("name", v)} />
            <Field enterOrder={2} label="Group" value={form.item_group ?? ""} onChange={(v) => set("item_group", v)} />
            <Field enterOrder={3} label="Variety" value={form.variety ?? ""} onChange={(v) => set("variety", v)} />
            <Field enterOrder={4} label="Unit" value={form.unit ?? ""} onChange={(v) => set("unit", v)} />
            <Field enterOrder={5} label="HSN Code" value={form.hsn_code ?? ""} onChange={(v) => set("hsn_code", v)} />
            <Field enterOrder={6} label="Market Fee %" value={form.market_pct ?? ""} onChange={(v) => set("market_pct", v)} />
            <Field enterOrder={7} label="RDF Fee %" value={form.rdf_fee_pct ?? ""} onChange={(v) => set("rdf_fee_pct", v)} />
            <Field enterOrder={8} label="GST Type" value={form.gst_type ?? ""} onChange={(v) => set("gst_type", v)} />
          </>
        );
      case "Account Master":
        return (
          <>
            {mode === "modify" && (
              <Autocomplete
                entityType="party"
                label="Select account / party to modify"
                required
                value={modifyParty}
                onSelect={(value) => {
                  setModifyParty(value);
                  if (value?.account_id) {
                    setForm((current) => ({ ...current, account_id: value.account_id ?? "" }));
                  }
                }}
              />
            )}
            <Field enterOrder={1} label="Account Name" value={form.name ?? ""} onChange={(v) => set("name", v)} />
            <Field enterOrder={2} label="Short Name" value={form.short_name ?? ""} onChange={(v) => set("short_name", v)} />
            <Field enterOrder={3} label="Print Name" value={form.print_name ?? ""} onChange={(v) => set("print_name", v)} />
            <Field enterOrder={4} label="Group Name" value={form.group_name ?? ""} onChange={(v) => set("group_name", v)} />
            <InlineField label="Party Type">
              <select className="w-full rounded border px-1 py-0.5" data-enter-order={5} value={form.party_type ?? "farmer"} onChange={(e) => set("party_type", e.target.value)}>
                <option value="farmer">Farmer</option>
                <option value="purchaser">Purchaser</option>
                <option value="customer">Customer</option>
                <option value="supplier">Supplier</option>
                <option value="commission_agent">Commission Agent</option>
                <option value="transporter">Transporter</option>
              </select>
            </InlineField>
            <InlineField label="GSTIN">
              <div className="flex gap-1">
                <input
                  className="w-full rounded border px-1 py-0.5"
                  data-enter-order={6}
                  maxLength={15}
                  value={form.gstin ?? ""}
                  onChange={(event) => set("gstin", event.target.value.toUpperCase())}
                />
                <button disabled={gstBusy} type="button" onClick={() => void fetchGst()}>
                  {gstBusy ? "…" : "Fetch"}
                </button>
              </div>
            </InlineField>
            <Field enterOrder={7} label="PAN" value={form.pan ?? ""} onChange={(v) => set("pan", v)} />
            <Field enterOrder={8} label="Address" value={form.address ?? ""} onChange={(v) => set("address", v)} />
            <Field enterOrder={9} label="City" value={form.city ?? ""} onChange={(v) => set("city", v)} />
            <Field enterOrder={10} label="Mobile" value={form.mobile1 ?? ""} onChange={(v) => set("mobile1", v)} />
            <Field enterOrder={11} label="Father / Group" value={form.father_name ?? ""} onChange={(v) => set("father_name", v)} />
            <Field enterOrder={12} label="Opening Balance" value={form.opening_balance ?? ""} onChange={(v) => set("opening_balance", v)} />
            <InlineField label="Dr/Cr">
              <select className="w-full rounded border px-1 py-0.5" data-enter-order={13} value={form.opening_side ?? "Dr"} onChange={(e) => set("opening_side", e.target.value)}>
                <option value="Dr">Dr</option>
                <option value="Cr">Cr</option>
              </select>
            </InlineField>
          </>
        );
      case "Expenses Master Define":
        return (
          <>
            <Field enterOrder={1} label="Master Name" value={form.name ?? ""} onChange={(v) => set("name", v)} />
            <Field enterOrder={2} label="Mandi Name" value={form.mandi_name ?? ""} onChange={(v) => set("mandi_name", v)} />
            <label className="block text-xs font-semibold">
              Expense Lines (JSON array)
              <textarea
                className="mt-1 w-full rounded border px-1 py-0.5 font-mono text-xs"
                data-enter-order={3}
                rows={6}
                value={expenseLines}
                onChange={(event) => setExpenseLines(event.target.value)}
              />
            </label>
          </>
        );
      case "Stock Entry Master":
        return (
          <>
            <div data-enter-order={1}>
              <Autocomplete entityType="commodity" label="Item Name" required value={commodity} onSelect={setCommodity} />
            </div>
            <Field enterOrder={2} label="Unit" value={form.unit ?? ""} onChange={(v) => set("unit", v)} />
            <Field enterOrder={3} label="Bags" value={form.bags ?? ""} onChange={(v) => set("bags", v)} />
            <Field enterOrder={4} label="Weight/Qty" value={form.quantity ?? ""} onChange={(v) => set("quantity", v)} />
            <Field enterOrder={5} label="Rate" value={form.rate ?? ""} onChange={(v) => set("rate", v)} />
            <Field enterOrder={6} label="Amount" value={form.amount ?? ""} onChange={(v) => set("amount", v)} />
          </>
        );
      default:
        return <p>This master screen will be added in the next batch.</p>;
    }
  })();

  return (
    <>
      <TransactionScreen
        grid={<div className="master-form-grid grid grid-cols-2 gap-2">{fields}</div>}
        header={<span className="text-xs text-[#37687a]">F3 Save · Esc Close</span>}
        title={screenTitle}
        onExit={onExit}
        onSave={(event) => void save(event)}
      />
      {message && (
        <MessageDialog message={message} onConfirm={() => setMessage("")} />
      )}
      {success && (
        <MessageDialog
          message="Data has been Successfully Saved"
          onConfirm={() => {
            setSuccess(false);
            onExit();
          }}
        />
      )}
    </>
  );
}

export { isMasterWindow as isMasterScreen } from "../windowRouting";

export default MasterForms;
