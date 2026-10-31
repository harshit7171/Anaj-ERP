import type { DesktopApi, Result } from "./types";

const TOKEN_KEY = "anajLanToken";
const SERVER_KEY = "anajLanServerUrl";

export function storedLanServerUrl(): string {
  return localStorage.getItem(SERVER_KEY) ?? "http://127.0.0.1:8765";
}

export function setLanServerUrl(url: string): void {
  localStorage.setItem(SERVER_KEY, url.replace(/\/$/, ""));
}

export function clearLanSession(): void {
  sessionStorage.removeItem(TOKEN_KEY);
}

export function hasLanSession(): boolean {
  return Boolean(sessionStorage.getItem(TOKEN_KEY));
}

export async function lanLogin(
  serverUrl: string,
  username: string,
  password: string,
): Promise<Result & { token?: string; user?: Record<string, unknown> }> {
  const base = serverUrl.replace(/\/$/, "");
  const response = await fetch(`${base}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const payload = (await response.json()) as Result & {
    token?: string;
    user?: Record<string, unknown>;
  };
  if (response.ok && payload.ok && payload.token) {
    sessionStorage.setItem(TOKEN_KEY, payload.token);
    setLanServerUrl(base);
  }
  return payload;
}

function createRemoteApi(serverUrl: string): DesktopApi {
  const base = serverUrl.replace(/\/$/, "");

  async function rpc(method: string, params: Record<string, unknown> = {}): Promise<Result> {
    const token = sessionStorage.getItem(TOKEN_KEY);
    if (!token) {
      return { ok: false, error: "Office login required" };
    }
    const response = await fetch(`${base}/api/v1/rpc`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ method, params }),
    });
    const payload = (await response.json()) as Result;
    if (!response.ok) {
      return {
        ok: false,
        error: String((payload as { detail?: string }).detail ?? payload.error ?? "Request failed"),
      };
    }
    return payload;
  }

  const api = {
    health: async () => {
      const response = await fetch(`${base}/health`);
      return (await response.json()) as Result & { installation_id?: string };
    },
    license_status: () => rpc("license_status"),
    install_license: (token: string) => rpc("install_license", { token }),
    list_companies: () => rpc("list_companies"),
    create_company: (name: string, startYear: number, companyProfile = "standard") =>
      rpc("create_company", { name, start_year: startYear, company_profile: companyProfile }),
    list_financial_years: (companyId: string) =>
      rpc("list_financial_years", { company_id: companyId }),
    select_context: (companyId: string, yearId: string) =>
      rpc("select_context", { company_id: companyId, financial_year_id: yearId }),
    compliance_status: () => rpc("compliance_status"),
    dashboard_summary: () => rpc("dashboard_summary"),
    farmer_credit_dashboard: (group?: string, query?: string) =>
      rpc("farmer_credit_dashboard", { group: group ?? "", query: query ?? "" }),
    list_charge_rules: (transactionType?: string, asOfDate?: string) =>
      rpc("list_charge_rules", {
        transaction_type: transactionType ?? "",
        as_of_date: asOfDate ?? "",
      }),
    revise_charge_rule: (chargeRuleId: string, payload: Record<string, unknown>) =>
      rpc("revise_charge_rule", { charge_rule_id: chargeRuleId, payload }),
    check_credit_limit: (payload: Record<string, unknown>) => rpc("check_credit_limit", payload),
    list_agricultural_groups: () => rpc("list_agricultural_groups"),
    update_party: (partyId: string, payload: Record<string, unknown>) =>
      rpc("update_party", { party_id: partyId, payload }),
    create_party: (payload: Record<string, unknown>) => rpc("create_party", { payload }),
    create_account: (name: string, accountType: string) =>
      rpc("create_account", { name, account_type: accountType }),
    create_commodity: (payload: Record<string, unknown>) => rpc("create_commodity", { payload }),
    create_charge_rule: (payload: Record<string, unknown>) =>
      rpc("create_charge_rule", { payload }),
    search_master: (entityType: string, query: string, limit?: number) =>
      rpc("search_master", { entity_type: entityType, query, limit: limit ?? 20 }),
    post_voucher: (payload: Record<string, unknown>) => rpc("post_voucher", { payload }),
    post_document: (payload: Record<string, unknown>) => rpc("post_document", { payload }),
    calculate_document: (payload: Record<string, unknown>) =>
      rpc("calculate_document", { payload }),
    next_document_number: (documentType: string) =>
      rpc("next_document_number", { document_type: documentType }),
    print_document: () => Promise.resolve({ ok: false, error: "Print from LAN client uses server PDF paths only" }),
    trial_balance: () => rpc("trial_balance"),
    stock_balance: () => rpc("stock_balance"),
    tax_register: (from: string, to: string, family: string) =>
      rpc("tax_register", { date_from: from, date_to: to, tax_family: family }),
    calculate_interest: (accountId: string, from: string, to: string, rate: string) =>
      rpc("calculate_interest", {
        account_id: accountId,
        date_from: from,
        date_to: to,
        annual_rate: rate,
      }),
    create_backup: (destination: string) => rpc("create_backup", { destination }),
    restore_new_company: (source: string) => rpc("restore_new_company", { source }),
    import_master_csv: (entityType: string, source: string, dryRun?: boolean) =>
      rpc("import_master_csv", {
        entity_type: entityType,
        source,
        dry_run: dryRun ?? true,
      }),
    reconcile_company: () => rpc("reconcile_company"),
    run_report: (reportKey: string, params: Record<string, unknown>) =>
      rpc("run_report", { report_key: reportKey, params }),
    find_accounts: (query?: string, city?: string, party_type?: string) =>
      rpc("find_accounts", { query: query ?? "", city: city ?? "", party_type: party_type ?? "" }),
    save_stock_adjustment: (payload: Record<string, unknown>) =>
      rpc("save_stock_adjustment", { payload }),
    get_company_settings: () => rpc("get_company_settings"),
    save_company_settings: (settings: Record<string, unknown>) =>
      rpc("save_company_settings", { settings }),
    list_prefix_settings: () => rpc("list_prefix_settings"),
    save_prefix_setting: (documentType: string, prefix: string, nextNumber: number) =>
      rpc("save_prefix_setting", {
        document_type: documentType,
        prefix,
        next_number: nextNumber,
      }),
    list_lan_users: () => rpc("list_lan_users"),
    save_lan_user: (payload: Record<string, unknown>) => rpc("save_lan_user", { payload }),
    set_company_profile: (companyId: string, companyProfile: string) =>
      rpc("set_company_profile", { company_id: companyId, company_profile: companyProfile }),
    print_cash_book_register: (cashAccountId: string, dateFrom: string, dateTo: string) =>
      rpc("print_cash_book_register", {
        cash_account_id: cashAccountId,
        date_from: dateFrom,
        date_to: dateTo,
      }),
    print_day_book_register: (dateFrom: string, dateTo: string) =>
      rpc("print_day_book_register", { date_from: dateFrom, date_to: dateTo }),
    print_voucher: (voucherId: string) => rpc("print_voucher", { voucher_id: voucherId }),
    run_diagnostics: () => rpc("run_diagnostics"),
    merge_parties: (sourcePartyId: string, targetPartyId: string) =>
      rpc("merge_parties", { source_party_id: sourcePartyId, target_party_id: targetPartyId }),
    whatsapp_for_document: (documentId: string) =>
      rpc("whatsapp_for_document", { document_id: documentId }),
    whatsapp_payment_reminder: (partyId: string) =>
      rpc("whatsapp_payment_reminder", { party_id: partyId }),
    open_whatsapp_url: (url: string) => rpc("open_whatsapp_url", { url }),
    generate_reminder_letters: (asOfDate: string, destination: string) =>
      rpc("generate_reminder_letters", { as_of_date: asOfDate, destination }),
    import_bank_statement: (source: string, dryRun?: boolean) =>
      rpc("import_bank_statement", { source, dry_run: dryRun ?? true }),
    attach_document_file: (documentId: string, source: string) =>
      rpc("attach_document_file", { document_id: documentId, source }),
    list_document_attachments: (documentId: string) =>
      rpc("list_document_attachments", { document_id: documentId }),
    print_cover_address: (partyId: string, destination: string) =>
      rpc("print_cover_address", { party_id: partyId, destination }),
    blended_average_cost: (commodityId: string, dateFrom: string, dateTo: string) =>
      rpc("blended_average_cost", {
        commodity_id: commodityId,
        date_from: dateFrom,
        date_to: dateTo,
      }),
    lookup_gstin: (gstin: string) => rpc("lookup_gstin", { gstin }),
    get_party_master: (partyId: string) => rpc("get_party_master", { party_id: partyId }),
    get_account_master: (accountId: string) => rpc("get_account_master", { account_id: accountId }),
    delete_account_master: (accountId: string) => rpc("delete_account_master", { account_id: accountId }),
    save_account_master: (payload: Record<string, unknown>) =>
      rpc("save_account_master", { payload }),
    list_narrations: () => rpc("list_narrations"),
    get_narration: (narration_id: string) => rpc("get_narration", { narration_id }),
    save_narration: (payload: Record<string, unknown>) =>
      rpc("save_narration", { payload }),
    delete_narration: (narration_id: string) =>
      rpc("delete_narration", { narration_id }),
    list_cities: () => rpc("list_cities"),
    get_city: (city_id: string) => rpc("get_city", { city_id }),
    save_city: (payload: Record<string, unknown>) => rpc("save_city", { payload }),
    delete_city: (city_id: string) => rpc("delete_city", { city_id }),
    list_transports: () => rpc("list_transports"),
    get_transport: (transport_id: string) => rpc("get_transport", { transport_id }),
    save_transport: (payload: Record<string, unknown>) =>
      rpc("save_transport", { payload }),
    delete_transport: (transport_id: string) =>
      rpc("delete_transport", { transport_id }),
    list_banks: () => rpc("list_banks"),
    get_bank: (bank_key: string) => rpc("get_bank", { bank_key }),
    save_bank: (payload: Record<string, unknown>) => rpc("save_bank", { payload }),
    delete_bank: (bank_key: string) => rpc("delete_bank", { bank_key }),
    list_ifsc_codes: () => rpc("list_ifsc_codes"),
    get_ifsc_code: (ifsc_key: string) => rpc("get_ifsc_code", { ifsc_key }),
    save_ifsc_code: (payload: Record<string, unknown>) =>
      rpc("save_ifsc_code", { payload }),
    delete_ifsc_code: (ifsc_key: string) => rpc("delete_ifsc_code", { ifsc_key }),
    list_stock_entries: (entry_kind?: string) =>
      rpc("list_stock_entries", { entry_kind: entry_kind ?? "" }),
    get_stock_entry_master: (args: {
      stock_entry_id?: string;
      entry_kind?: string;
      entry_date?: string;
      search_item?: string;
    }) => rpc("get_stock_entry_master", args),
    save_stock_entry_master: (payload: Record<string, unknown>) =>
      rpc("save_stock_entry_master", { payload }),
    delete_stock_entry_master: (stock_entry_id: string) =>
      rpc("delete_stock_entry_master", { stock_entry_id }),
    list_items: () => rpc("list_items"),
    get_item: (commodity_id: string) => rpc("get_item", { commodity_id }),
    delete_item: (commodity_id: string) => rpc("delete_item", { commodity_id }),
    save_item_master: (payload: Record<string, unknown>) =>
      rpc("save_item_master", { payload }),
    list_trading_accounts: () => rpc("list_trading_accounts"),
    get_trading_account: (trading_account_id: string) =>
      rpc("get_trading_account", { trading_account_id }),
    save_trading_account: (payload: Record<string, unknown>) =>
      rpc("save_trading_account", { payload }),
    delete_trading_account: (trading_account_id: string) =>
      rpc("delete_trading_account", { trading_account_id }),
    list_expense_masters: () => rpc("list_expense_masters"),
    get_expense_master: (expense_master_id: string) =>
      rpc("get_expense_master", { expense_master_id }),
    save_expense_master: (payload: Record<string, unknown>) =>
      rpc("save_expense_master", { payload }),
    delete_expense_master: (expense_master_id: string) =>
      rpc("delete_expense_master", { expense_master_id }),
    list_cheque_print_settings: () => rpc("list_cheque_print_settings"),
    get_cheque_print_setting: (setting_key: string) =>
      rpc("get_cheque_print_setting", { setting_key }),
    save_cheque_print_setting: (payload: Record<string, unknown>) =>
      rpc("save_cheque_print_setting", { payload }),
    delete_cheque_print_setting: (setting_key: string) =>
      rpc("delete_cheque_print_setting", { setting_key }),
    list_i_form_expense_defines: (commodity_id?: string) =>
      rpc("list_i_form_expense_defines", { commodity_id: commodity_id ?? "" }),
    get_i_form_expense_define: (commodity_id: string, effective_date: string) =>
      rpc("get_i_form_expense_define", { commodity_id, effective_date }),
    save_i_form_expense_define: (payload: Record<string, unknown>) =>
      rpc("save_i_form_expense_define", { payload }),
    delete_i_form_expense_define: (define_id: string) =>
      rpc("delete_i_form_expense_define", { define_id }),
    discover_lan_servers: (timeout_seconds?: number) =>
      rpc("discover_lan_servers", { timeout_seconds: timeout_seconds ?? 2.5 }),
    fetch_mandi_bhav: (state?: string, commodity?: string, limit?: number) =>
      rpc("fetch_mandi_bhav", { state: state ?? "", commodity: commodity ?? "", limit: limit ?? 40 }),
    auction_board_snapshot: () => rpc("auction_board_snapshot"),
    upsert_auction_lot: (payload: Record<string, unknown>) =>
      rpc("upsert_auction_lot", { payload }),
    place_auction_bid: (payload: Record<string, unknown>) => rpc("place_auction_bid", { payload }),
    close_auction_lot: (lot_id: string) => rpc("close_auction_lot", { lot_id }),
    start_cloud_oauth: (provider: string) => rpc("start_cloud_oauth", { provider }),
    poll_cloud_oauth: (provider: string, device_code: string) =>
      rpc("poll_cloud_oauth", { provider, device_code }),
    run_encrypted_cloud_backup: (destination: string) =>
      rpc("run_encrypted_cloud_backup", { destination }),
    acquire_document_lock: (resource_key: string, holder_label?: string) =>
      rpc("acquire_document_lock", { resource_key, holder_label: holder_label ?? "" }),
    release_document_lock: (resource_key: string) =>
      rpc("release_document_lock", { resource_key }),
  };

  return api as DesktopApi;
}

export function bindRemoteApi(): DesktopApi | null {
  if (!hasLanSession()) return null;
  return createRemoteApi(storedLanServerUrl());
}

export function installRemoteApiBridge(): void {
  const remote = bindRemoteApi();
  if (!remote) return;
  window.pywebview = { api: remote };
}
