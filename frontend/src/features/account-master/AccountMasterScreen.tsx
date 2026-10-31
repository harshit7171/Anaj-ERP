import { FormEvent, useEffect, useRef, useState } from "react";

import DeleteConfirmModal from "../../components/DeleteConfirmModal";
import useFieldFocusHandlers from "../../hooks/useFieldFocusHandlers";
import { useFormEnterFlow } from "../../hooks/useFormEnterFlow";
import { accountMasterApi } from "./api";
import {
  AC_CATEGORIES,
  FARMER_ARTHIA,
  LOCAL_CENTRAL,
  MAIN_HEADS,
  OPENING_SIDES,
  PARTY_GST_TYPES,
  TDS_DEDUCTEE,
  YES_NO,
} from "./constants";
import { ComboboxInput, FieldLabel, TextArea, TextInput } from "./components/Fields";
import { combinedAddress, emptyForm, openingPaise, recordToForm } from "./formState";
import type { FormState } from "./types";

const api = accountMasterApi;

export default function AccountMasterScreen({
  mode,
  onExit,
}: {
  mode: "add" | "modify";
  onExit(): void;
}) {
  const formRef = useRef<HTMLFormElement>(null);
  const accountIdRef = useRef<HTMLInputElement>(null);
  const [form, setForm] = useState<FormState>(() => emptyForm());
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [findOpen, setFindOpen] = useState(false);
  const [findQuery, setFindQuery] = useState("");
  const [findRows, setFindRows] = useState<Record<string, unknown>[]>([]);
  const [findBusy, setFindBusy] = useState(false);
  const [gstBusy, setGstBusy] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [accountLoaded, setAccountLoaded] = useState(mode !== "modify");

  const fieldsLocked = mode === "modify" && !accountLoaded;

  useFormEnterFlow(formRef, true);
  useFieldFocusHandlers(formRef, true);

  useEffect(() => {
    setForm(emptyForm());
    setStatus("");
    setError("");
    setAccountLoaded(mode !== "modify");
    if (mode === "modify") {
      setFindOpen(true);
      setFindQuery("");
      setFindRows([]);
    }
  }, [mode]);

  function set(key: string, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function loadRecord(party: Record<string, unknown>) {
    setForm(recordToForm(party));
    setAccountLoaded(true);
    setStatus("Account loaded — you can edit and save (F3).");
    setError("");
  }

  async function loadByAccountId(accountId: string) {
    const clean = accountId.trim();
    if (!clean) {
      setError("Enter an Account ID to find.");
      return;
    }
    const bridge = api();
    if (!bridge) {
      setError("Desktop API is not available.");
      return;
    }
    let response = await bridge.get_account_master?.(clean);
    if (!response?.ok && bridge.get_party_master) {
      response = await bridge.get_party_master(clean);
    }
    if (!response?.ok || !response.party) {
      setError(response?.error ?? "Account not found.");
      return;
    }
    await loadRecord(response.party);
    setStatus("Account loaded.");
  }

  async function runFind(searchText?: string) {
    const bridge = api();
    if (!bridge) {
      setError("Desktop API is not available.");
      return;
    }
    const query = (searchText ?? form.account_id ?? findQuery).trim();
    if (!query) {
      setFindOpen(true);
      return;
    }
    if (mode === "modify" && !findOpen && query.length >= 8) {
      await loadByAccountId(query);
      return;
    }
    setFindBusy(true);
    const response = await bridge.find_accounts?.(query);
    setFindBusy(false);
    if (!response?.ok) {
      setError(response?.error ?? "Find failed.");
      return;
    }
    const rows = response.rows ?? [];
    if (rows.length === 1 && rows[0].party_id) {
      const detail = await bridge.get_party_master?.(String(rows[0].party_id));
      if (detail?.ok && detail.party) {
        await loadRecord(detail.party);
        setStatus("Account loaded.");
        setFindOpen(false);
        return;
      }
    }
    setFindRows(rows);
    setFindQuery(query);
    setFindOpen(true);
  }

  async function fetchGst() {
    const gstin = form.gstin.trim();
    if (gstin.length !== 15) {
      setError("Enter a 15-character GSTIN first.");
      return;
    }
    setGstBusy(true);
    const response = await api()?.lookup_gstin?.(gstin);
    setGstBusy(false);
    if (!response?.ok || !response.taxpayer) {
      setError(response?.error ?? "GST lookup failed.");
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
    }));
    setStatus(taxpayer.status ? `GST status: ${taxpayer.status}` : "GST details loaded.");
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setError("");
    const bridge = api();
    if (!bridge?.save_account_master) {
      setError("Desktop API is not available.");
      return;
    }
    if (mode === "modify" && (!accountLoaded || !form.account_id.trim())) {
      setError("Select an account with Find (F5) before saving changes.");
      return;
    }
    if (!form.name.trim()) {
      setError("Account Name is required.");
      return;
    }
    const opening = openingPaise(form);
    const payload: Record<string, unknown> = {
      ...form,
      account_id: mode === "modify" ? form.account_id || undefined : undefined,
      party_id: mode === "modify" ? form.party_id || undefined : undefined,
      party_type: "farmer",
      address: combinedAddress(form),
      opening_debit_paise: opening.debit,
      opening_credit_paise: opening.credit,
    };
    const response = await bridge.save_account_master(payload);
    if (!response?.ok) {
      setError(response?.error ?? "Save failed.");
      return;
    }
    setStatus("Data has been Successfully Saved");
    if (mode === "add") {
      setForm(emptyForm());
      window.requestAnimationFrame(() => accountIdRef.current?.focus());
    }
  }

  async function confirmDelete() {
    const bridge = api();
    if (!bridge?.delete_account_master || !form.account_id) {
      setError("Nothing to delete.");
      setDeleteOpen(false);
      return;
    }
    const response = await bridge.delete_account_master(form.account_id);
    setDeleteOpen(false);
    if (!response?.ok) {
      setError(response?.error ?? "Delete failed.");
      return;
    }
    setStatus("Account deleted.");
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
      if (event.key === "F5") {
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
        className="account-master-screen"
        data-account-master-form
        onSubmit={(event) => void save(event)}
      >
        <div className="account-master-toolbar">
          <div className="account-master-toolbar-left">
            <FieldLabel label="Account ID">
              <TextInput
                ref={accountIdRef}
                enterOrder={1}
                value={form.account_id}
                onChange={(value) => set("account_id", value)}
              />
            </FieldLabel>
            <button className="account-master-btn" type="button" onClick={() => void runFind()}>
              Find (F5)
            </button>
          </div>
          <div className="account-master-toolbar-actions">
            <button
              className="account-master-btn account-master-btn-primary"
              disabled={mode === "modify" && !accountLoaded}
              type="submit"
            >
              Save (F3)
            </button>
            <button className="account-master-btn" type="button" onClick={onExit}>
              Cancel (F4)
            </button>
            {mode === "modify" && (
              <button
                className="account-master-btn account-master-btn-danger"
                disabled={!accountLoaded}
                type="button"
                onClick={() => setDeleteOpen(true)}
              >
                Delete
              </button>
            )}
          </div>
        </div>

        {fieldsLocked && (
          <div className="account-master-hint" role="status">
            Use <strong>Find (F5)</strong> to select an account. Fields stay read-only until an account is loaded.
          </div>
        )}

        <div className={`account-master-body${fieldsLocked ? " is-locked" : ""}`}>
          <fieldset className="account-master-fields" disabled={fieldsLocked}>
          <div className="account-master-row account-master-row-3">
            <FieldLabel className="span-2" label="Account Name">
              <TextInput enterOrder={2} value={form.name} onChange={(v) => set("name", v)} />
            </FieldLabel>
            <FieldLabel label="Main Head">
              <ComboboxInput
                aria-label="Main Head account group"
                enterOrder={3}
                options={MAIN_HEADS}
                placeholder="Select group (Bank, Debtors, Sales…)"
                value={form.main_head}
                onChange={(v) => set("main_head", v)}
              />
            </FieldLabel>
          </div>

          <div className="account-master-row account-master-row-4">
            <FieldLabel label="Party GST Type">
              <ComboboxInput
                enterOrder={4}
                options={PARTY_GST_TYPES}
                value={form.party_gst_type}
                onChange={(v) => set("party_gst_type", v)}
              />
            </FieldLabel>
            <button
              className="account-master-btn account-master-gst-btn"
              disabled={fieldsLocked || gstBusy}
              type="button"
              onClick={() => void fetchGst()}
            >
              {gstBusy ? "…" : "Get GST Details"}
            </button>
            <FieldLabel label="Short Name">
              <TextInput enterOrder={5} value={form.short_name} onChange={(v) => set("short_name", v)} />
            </FieldLabel>
            <FieldLabel label="A/c Category">
              <ComboboxInput
                enterOrder={6}
                options={AC_CATEGORIES}
                value={form.ac_category}
                onChange={(v) => set("ac_category", v)}
              />
            </FieldLabel>
          </div>

          <div className="account-master-row account-master-row-4">
            <FieldLabel className="span-2" label="Print Name">
              <TextInput enterOrder={7} value={form.print_name} onChange={(v) => set("print_name", v)} />
            </FieldLabel>
            <FieldLabel label="Opening Bal">
              <div className="account-master-split">
                <TextInput
                  enterOrder={8}
                  value={form.opening_balance}
                  onChange={(v) => set("opening_balance", v)}
                />
                <ComboboxInput
                  aria-label="Opening balance type"
                  className="account-master-opening-side"
                  enterOrder={9}
                  options={OPENING_SIDES}
                  value={form.opening_side}
                  onChange={(v) => set("opening_side", v)}
                />
              </div>
            </FieldLabel>
            <FieldLabel label="Show Tcs Msg">
              <ComboboxInput
                enterOrder={10}
                options={YES_NO}
                value={form.show_tcs_msg}
                onChange={(v) => set("show_tcs_msg", v)}
              />
            </FieldLabel>
          </div>

          <div className="account-master-row account-master-row-address">
            <div className="account-master-address-col">
              <FieldLabel label="Address">
                <TextInput enterOrder={11} value={form.address} onChange={(v) => set("address", v)} />
              </FieldLabel>
              <FieldLabel label="">
                <TextInput enterOrder={12} value={form.address_line2} onChange={(v) => set("address_line2", v)} />
              </FieldLabel>
              <FieldLabel label="">
                <TextInput enterOrder={13} value={form.address_line3} onChange={(v) => set("address_line3", v)} />
              </FieldLabel>
              <FieldLabel label="City">
                <TextInput enterOrder={14} value={form.city} onChange={(v) => set("city", v)} />
              </FieldLabel>
              <FieldLabel label="Contact Person">
                <TextInput
                  enterOrder={15}
                  value={form.contact_person}
                  onChange={(v) => set("contact_person", v)}
                />
              </FieldLabel>
            </div>
            <div className="account-master-side-col">
              <FieldLabel label="A/c Code">
                <TextInput enterOrder={16} value={form.account_code} onChange={(v) => set("account_code", v)} />
              </FieldLabel>
              <FieldLabel label="Uniq ID">
                <TextInput enterOrder={17} value={form.uniq_id} onChange={(v) => set("uniq_id", v)} />
              </FieldLabel>
              <FieldLabel label="Distance (KMs)">
                <TextInput enterOrder={18} value={form.distance_kms} onChange={(v) => set("distance_kms", v)} />
              </FieldLabel>
              <FieldLabel label="Pin Code">
                <TextInput enterOrder={19} value={form.pincode} onChange={(v) => set("pincode", v)} />
              </FieldLabel>
              <FieldLabel label="Farmer/Aarthia">
                <ComboboxInput
                  enterOrder={20}
                  options={FARMER_ARTHIA}
                  value={form.farmer_arthia}
                  onChange={(v) => set("farmer_arthia", v)}
                />
              </FieldLabel>
            </div>
          </div>

          <div className="account-master-row account-master-row-4">
            <FieldLabel label="Phone">
              <TextInput enterOrder={21} value={form.phone} onChange={(v) => set("phone", v)} />
            </FieldLabel>
            <FieldLabel label="2nd Phone">
              <TextInput enterOrder={22} value={form.phone2} onChange={(v) => set("phone2", v)} />
            </FieldLabel>
            <FieldLabel label="Mobile">
              <TextInput enterOrder={23} value={form.mobile1} onChange={(v) => set("mobile1", v)} />
            </FieldLabel>
            <FieldLabel label="Mobile 2">
              <TextInput enterOrder={24} value={form.mobile2} onChange={(v) => set("mobile2", v)} />
            </FieldLabel>
          </div>

          <div className="account-master-row account-master-row-3">
            <FieldLabel label="Fax No.">
              <TextInput enterOrder={25} value={form.fax} onChange={(v) => set("fax", v)} />
            </FieldLabel>
            <FieldLabel label="Web">
              <TextInput enterOrder={26} value={form.web} onChange={(v) => set("web", v)} />
            </FieldLabel>
            <FieldLabel label="Email ID">
              <TextInput enterOrder={27} value={form.email} onChange={(v) => set("email", v)} />
            </FieldLabel>
          </div>

          <div className="account-master-row account-master-row-4">
            <FieldLabel className="span-2" label="Group Name">
              <TextInput enterOrder={28} value={form.group_name} onChange={(v) => set("group_name", v)} />
            </FieldLabel>
            <FieldLabel label="TDS Detuctee Co. Code">
              <ComboboxInput
                enterOrder={29}
                options={TDS_DEDUCTEE}
                value={form.tds_deductee_code}
                onChange={(v) => set("tds_deductee_code", v)}
              />
            </FieldLabel>
            <FieldLabel label="D.O.B">
              <TextInput enterOrder={30} value={form.dob} onChange={(v) => set("dob", v)} />
            </FieldLabel>
          </div>

          <div className="account-master-row account-master-row-4">
            <FieldLabel label="GST No.">
              <TextInput
                enterOrder={31}
                maxLength={15}
                value={form.gstin}
                onChange={(v) => set("gstin", v.toUpperCase())}
              />
            </FieldLabel>
            <FieldLabel label="PAN No.">
              <TextInput enterOrder={32} value={form.pan} onChange={(v) => set("pan", v.toUpperCase())} />
            </FieldLabel>
            <FieldLabel className="span-2" label="Aadhar No.">
              <div className="account-master-aadhar">
                <TextInput
                  enterOrder={33}
                  maxLength={4}
                  value={form.aadhar_part1}
                  onChange={(v) => set("aadhar_part1", v.replace(/\D/g, ""))}
                />
                <span>-</span>
                <TextInput
                  enterOrder={34}
                  maxLength={4}
                  value={form.aadhar_part2}
                  onChange={(v) => set("aadhar_part2", v.replace(/\D/g, ""))}
                />
                <span>-</span>
                <TextInput
                  enterOrder={35}
                  maxLength={4}
                  value={form.aadhar_part3}
                  onChange={(v) => set("aadhar_part3", v.replace(/\D/g, ""))}
                />
              </div>
            </FieldLabel>
          </div>

          <div className="account-master-row account-master-row-3">
            <FieldLabel label="TAN No.">
              <TextInput enterOrder={36} value={form.tan} onChange={(v) => set("tan", v)} />
            </FieldLabel>
            <FieldLabel label="TDS Rate">
              <TextInput enterOrder={37} value={form.tds_rate} onChange={(v) => set("tds_rate", v)} />
            </FieldLabel>
            <FieldLabel label="Trading A/c">
              <TextInput enterOrder={38} value={form.trading_ac} onChange={(v) => set("trading_ac", v)} />
            </FieldLabel>
          </div>

          <div className="account-master-row account-master-row-6">
            <FieldLabel label="Interest Rate">
              <TextInput enterOrder={39} value={form.interest_rate} onChange={(v) => set("interest_rate", v)} />
            </FieldLabel>
            <FieldLabel label="Depriciation Rate">
              <TextInput
                enterOrder={40}
                value={form.depreciation_rate}
                onChange={(v) => set("depreciation_rate", v)}
              />
            </FieldLabel>
            <FieldLabel label="Sec. Code">
              <TextInput enterOrder={41} value={form.sec_code} onChange={(v) => set("sec_code", v)} />
            </FieldLabel>
            <FieldLabel label="Local / Central">
              <ComboboxInput
                enterOrder={42}
                options={LOCAL_CENTRAL}
                value={form.local_central}
                onChange={(v) => set("local_central", v)}
              />
            </FieldLabel>
            <FieldLabel label="GP Rate">
              <TextInput enterOrder={43} value={form.gp_rate} onChange={(v) => set("gp_rate", v)} />
            </FieldLabel>
            <FieldLabel label="Profit Share">
              <TextInput enterOrder={44} value={form.profit_share} onChange={(v) => set("profit_share", v)} />
            </FieldLabel>
          </div>

          <div className="account-master-row account-master-row-4">
            <FieldLabel label="Bank A/c No.">
              <TextInput enterOrder={45} value={form.bank_ac_no} onChange={(v) => set("bank_ac_no", v)} />
            </FieldLabel>
            <FieldLabel label="Consolidate (Y/N)">
              <ComboboxInput
                enterOrder={46}
                options={YES_NO}
                value={form.consolidate_yn}
                onChange={(v) => set("consolidate_yn", v)}
              />
            </FieldLabel>
            <FieldLabel label="Bank IFSC">
              <TextInput enterOrder={47} value={form.bank_ifsc} onChange={(v) => set("bank_ifsc", v)} />
            </FieldLabel>
            <FieldLabel label="Lock Date">
              <TextInput enterOrder={48} value={form.lock_date} onChange={(v) => set("lock_date", v)} />
            </FieldLabel>
          </div>

          <div className="account-master-row account-master-row-2">
            <FieldLabel label="Main A/c">
              <TextInput enterOrder={49} value={form.main_ac} onChange={(v) => set("main_ac", v)} />
            </FieldLabel>
            <FieldLabel label="Remarks">
              <TextArea enterOrder={50} rows={2} value={form.remarks} onChange={(v) => set("remarks", v)} />
            </FieldLabel>
          </div>
          <div aria-hidden className="account-master-scroll-pad" />
          </fieldset>
        </div>

        <footer className="account-master-status">
          {error ? <span className="account-master-error">{error}</span> : null}
          {!error && status ? <span className="account-master-ok">{status}</span> : null}
        </footer>
      </form>

      {findOpen && (
        <div className="account-master-find-overlay" role="presentation">
          <div className="account-master-find-panel" role="dialog" aria-modal="true">
            <header>
              <strong>Find Account (F5)</strong>
              <button type="button" onClick={() => setFindOpen(false)} aria-label="Close">
                ×
              </button>
            </header>
            <form
              className="account-master-find-search"
              onSubmit={(event) => {
                event.preventDefault();
                void runFind(findQuery);
              }}
            >
              <input
                value={findQuery}
                onChange={(event) => setFindQuery(event.target.value)}
                placeholder="Name / phone / GSTIN / account id"
              />
              <button disabled={findBusy} type="submit">
                {findBusy ? "…" : "Search"}
              </button>
            </form>
            <div className="account-master-find-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>City</th>
                    <th>Phone</th>
                    <th>GSTIN</th>
                  </tr>
                </thead>
                <tbody>
                  {findRows.map((row) => (
                    <tr
                      key={String(row.party_id ?? row.account_id)}
                      tabIndex={0}
                      onDoubleClick={() => {
                        void (async () => {
                          const detail = await api()?.get_party_master?.(String(row.party_id));
                          if (detail?.ok && detail.party) {
                            await loadRecord(detail.party);
                            setFindOpen(false);
                            setStatus("Account loaded.");
                          }
                        })();
                      }}
                    >
                      <td>{String(row.name ?? row.account_name ?? "")}</td>
                      <td>{String(row.city ?? "")}</td>
                      <td>{String(row.phone ?? "")}</td>
                      <td>{String(row.gstin ?? "")}</td>
                    </tr>
                  ))}
                  {!findRows.length && (
                    <tr>
                      <td colSpan={4}>No matches — adjust search and try again.</td>
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
        recordLabel={form.name || "this account"}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => void confirmDelete()}
      />
    </>
  );
}
