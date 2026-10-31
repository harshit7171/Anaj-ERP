import type { FormState } from "./types";

export function emptyForm(): FormState {
  return {
    account_id: "",
    party_id: "",
    name: "",
    main_head: "",
    party_gst_type: "Unregistered",
    short_name: "",
    ac_category: "Good",
    print_name: "",
    opening_balance: "",
    opening_side: "Debit",
    show_tcs_msg: "Y",
    address: "",
    address_line2: "",
    address_line3: "",
    city: "",
    account_code: "",
    uniq_id: "",
    distance_kms: "",
    pincode: "",
    farmer_arthia: "N",
    contact_person: "",
    phone: "",
    phone2: "",
    mobile1: "",
    mobile2: "",
    fax: "",
    web: "",
    email: "",
    group_name: "",
    tds_deductee_code: "02-other than Companies",
    dob: "",
    gstin: "",
    pan: "",
    aadhar_part1: "",
    aadhar_part2: "",
    aadhar_part3: "",
    tan: "",
    tds_rate: "",
    trading_ac: "",
    interest_rate: "",
    depreciation_rate: "",
    sec_code: "",
    local_central: "Local",
    gp_rate: "",
    profit_share: "",
    bank_ac_no: "",
    consolidate_yn: "N",
    bank_ifsc: "",
    lock_date: "",
    main_ac: "",
    remarks: "",
  };
}

export function recordToForm(party: Record<string, unknown>): FormState {
  const base = emptyForm();
  for (const key of Object.keys(base)) {
    const value = party[key];
    if (value !== undefined && value !== null && value !== "") {
      base[key] = String(value);
    }
  }
  if (party.opening_side === "Dr") base.opening_side = "Debit";
  if (party.opening_side === "Cr") base.opening_side = "Credit";
  if (party.opening_balance !== undefined) {
    base.opening_balance = String(party.opening_balance);
  }
  return base;
}

export function openingPaise(form: FormState): { debit: number; credit: number } {
  const amount = Math.round(Number(form.opening_balance || 0) * 100);
  if (form.opening_side === "Credit") {
    return { debit: 0, credit: amount };
  }
  return { debit: amount, credit: 0 };
}

export function combinedAddress(form: FormState): string {
  return [form.address, form.address_line2, form.address_line3]
    .map((line) => line.trim())
    .filter(Boolean)
    .join("\n");
}
