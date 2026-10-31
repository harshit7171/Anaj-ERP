export type Result = {
  ok: boolean;
  error?: string;
  error_type?: string;
  [key: string]: unknown;
};

export type LookupItem = {
  id: string;
  label: string;
  gstin?: string;
  account_id?: string;
  account_name?: string;
  father_name?: string;
  agricultural_group?: string;
  village_name?: string;
  credit_limit_paise?: number;
};

export type CreditEvaluation = {
  party_id: string;
  party_name: string;
  credit_limit_paise: number;
  current_balance_paise: number;
  additional_debit_paise: number;
  projected_balance_paise: number;
  available_credit_paise: number | null;
  overage_paise: number;
  status: "normal" | "approaching" | "exceeded";
  limit_assigned: boolean;
  breached: boolean;
};

export type DesktopApi = {
  health(): Promise<Result & { installation_id?: string; license?: LicenseStatus }>;
  license_status(): Promise<Result & LicenseStatus>;
  install_license(token: string): Promise<Result & { license?: LicenseStatus }>;
  list_companies(): Promise<Result & { companies?: Company[] }>;
  create_company(
    name: string,
    startYear: number,
    companyProfile?: string,
  ): Promise<Result & { company?: Company }>;
  list_financial_years(companyId: string): Promise<Result & { financial_years?: FinancialYear[] }>;
  select_context(companyId: string, yearId: string): Promise<Result>;
  compliance_status(): Promise<Result & { compliance?: ComplianceStatus }>;
  dashboard_summary(): Promise<Result & { dashboard?: DashboardSummary }>;
  farmer_credit_dashboard(group?: string, query?: string): Promise<Result & { rows?: FarmerCreditRow[] }>;
  list_charge_rules(transactionType?: string, asOfDate?: string): Promise<Result & { charge_rules?: ChargeRule[] }>;
  revise_charge_rule(chargeRuleId: string, payload: Record<string, unknown>): Promise<Result>;
  check_credit_limit(payload: Record<string, unknown>): Promise<Result & { evaluation?: CreditEvaluation }>;
  list_agricultural_groups(): Promise<Result & { groups?: string[] }>;
  update_party(partyId: string, payload: Record<string, unknown>): Promise<Result>;
  create_party(payload: Record<string, unknown>): Promise<Result>;
  create_account(name: string, accountType: string): Promise<Result>;
  create_commodity(payload: Record<string, unknown>): Promise<Result>;
  create_charge_rule(payload: Record<string, unknown>): Promise<Result>;
  search_master(entityType: string, query: string, limit?: number): Promise<Result & { items?: LookupItem[] }>;
  post_voucher(payload: Record<string, unknown>): Promise<Result>;
  post_document(payload: Record<string, unknown>): Promise<Result>;
  calculate_document(payload: Record<string, unknown>): Promise<Result>;
  next_document_number(documentType: string): Promise<Result & { document_number?: string }>;
  print_document(documentId: string): Promise<Result>;
  trial_balance(): Promise<Result & { rows?: Record<string, unknown>[] }>;
  stock_balance(): Promise<Result & { rows?: Record<string, unknown>[] }>;
  tax_register(from: string, to: string, family: string): Promise<Result & { rows?: Record<string, unknown>[] }>;
  calculate_interest(accountId: string, from: string, to: string, rate: string): Promise<Result>;
  create_backup(destination: string): Promise<Result>;
  restore_new_company(source: string): Promise<Result>;
  import_master_csv(entityType: string, source: string, dryRun?: boolean): Promise<Result>;
  reconcile_company(): Promise<Result>;
  run_report(reportKey: string, params: Record<string, unknown>): Promise<Result>;
  find_accounts(query?: string, city?: string, party_type?: string): Promise<Result & { rows?: Record<string, unknown>[] }>;
  save_stock_adjustment(payload: Record<string, unknown>): Promise<Result>;
  get_company_settings(): Promise<Result & { settings?: Record<string, unknown> }>;
  save_company_settings(settings: Record<string, unknown>): Promise<Result>;
  list_prefix_settings(): Promise<Result & { prefixes?: Record<string, unknown>[] }>;
  save_prefix_setting(documentType: string, prefix: string, nextNumber: number): Promise<Result>;
  list_lan_users(): Promise<Result & { users?: Record<string, unknown>[] }>;
  save_lan_user(payload: Record<string, unknown>): Promise<Result>;
  delete_lan_user(userId: string): Promise<Result>;
  user_login(username: string, password: string): Promise<Result & { session?: Record<string, unknown> }>;
  user_logout(): Promise<Result>;
  user_login_status(): Promise<
    Result & {
      login_required?: boolean;
      logged_in?: boolean;
      session?: Record<string, unknown> | null;
    }
  >;
  user_session(): Promise<Result & { session?: Record<string, unknown> | null }>;
  list_user_permission_catalog(): Promise<Result & { catalog?: Record<string, unknown>[] }>;
  get_user_permissions(userId: string): Promise<Result & { permissions?: Record<string, string> }>;
  save_user_permissions(
    userId: string,
    grants: Record<string, unknown>[],
  ): Promise<Result & { permissions?: Record<string, string> }>;
  set_company_profile(companyId: string, companyProfile: string): Promise<Result>;
  print_cash_book_register(cashAccountId: string, dateFrom: string, dateTo: string): Promise<Result>;
  print_day_book_register(dateFrom: string, dateTo: string): Promise<Result>;
  print_voucher(voucherId: string): Promise<Result>;
  run_diagnostics(): Promise<Result & { diagnostics?: Record<string, unknown> }>;
  merge_parties(sourcePartyId: string, targetPartyId: string): Promise<Result>;
  whatsapp_for_document(documentId: string): Promise<Result & { url?: string }>;
  whatsapp_payment_reminder(partyId: string): Promise<Result & { url?: string }>;
  open_whatsapp_url(url: string): Promise<Result>;
  generate_reminder_letters(asOfDate: string, destination: string): Promise<Result & { path?: string }>;
  import_bank_statement(source: string, dryRun?: boolean): Promise<Result>;
  attach_document_file(documentId: string, source: string): Promise<Result>;
  list_document_attachments(
    documentId: string,
  ): Promise<Result & { attachments?: { attachment_id: string; file_name: string; created_at?: string }[] }>;
  print_cover_address(partyId: string, destination: string): Promise<Result & { path?: string }>;
  blended_average_cost(
    commodityId: string,
    dateFrom: string,
    dateTo: string,
  ): Promise<Result & { blended_rate_paise?: number; lots?: Record<string, unknown>[] }>;
  lookup_gstin(gstin: string): Promise<Result & { taxpayer?: Record<string, string> }>;
  get_party_master(partyId: string): Promise<Result & { party?: Record<string, unknown> }>;
  discover_lan_servers?(
    timeout_seconds?: number,
  ): Promise<Result & { servers?: { url: string; office_name?: string }[] }>;
  fetch_mandi_bhav?(
    state?: string,
    commodity?: string,
    limit?: number,
  ): Promise<Result & { rows?: Record<string, string>[]; source?: string; notice?: string }>;
  auction_board_snapshot?(): Promise<Result & { lots?: Record<string, unknown>[] }>;
  upsert_auction_lot?(payload: Record<string, unknown>): Promise<Result>;
  place_auction_bid?(payload: Record<string, unknown>): Promise<Result>;
  close_auction_lot?(lot_id: string): Promise<Result>;
  start_cloud_oauth?(provider: string): Promise<
    Result & { user_code?: string; verification_url?: string; device_code?: string }
  >;
  poll_cloud_oauth?(provider: string, device_code: string): Promise<Result & { pending?: boolean }>;
  run_encrypted_cloud_backup?(destination: string): Promise<Result & { encrypted_path?: string }>;
  acquire_document_lock?(resource_key: string, holder_label?: string): Promise<Result>;
  release_document_lock?(resource_key: string): Promise<Result>;
};

export type Company = {
  company_id: string;
  name: string;
  company_profile?: string;
};
export type FinancialYear = {
  financial_year_id: string;
  label: string;
  is_locked: boolean;
};

export type LicenseStatus = {
  valid?: boolean;
  writable?: boolean;
  phase?:
    | "active"
    | "warning"
    | "expired"
    | "clock_tamper"
    | "unlicensed"
    | "not_started"
    | "demo"
    | "demo_expired";
  reason?: string;
  warning_message?: string;
};

export type ComplianceStatus = {
  show_tds_reminder: boolean;
  tds_pending_count: number;
  tds_liability_paise: number;
  open_eway_bills: number;
  month_label: string;
};

export type FarmerCreditRow = {
  party_id: string;
  group_name: string;
  farmer_name: string;
  father_name: string;
  village_name: string;
  current_balance_paise: number;
  credit_limit_paise: number;
  available_credit_paise: number | null;
  status: "normal" | "approaching" | "exceeded";
  limit_assigned: boolean;
};

export type DashboardSummary = {
  inward_trends: { month: string; bags_scaled: number; quantity_scaled: number }[];
  farmer_risk_watchlist: FarmerCreditRow[];
  compliance: ComplianceStatus;
  executive?: Record<string, unknown>;
  threshold_alerts?: { type?: string; message?: string }[];
};

export type ChargeRule = {
  charge_rule_id: string;
  code: string;
  label: string;
  transaction_type: string;
  rate_decimal: string;
  basis: string;
  mode: string;
  is_tax: number;
  effective_from: string;
  effective_to?: string | null;
};

declare global {
  interface Window {
    pywebview?: { api: DesktopApi };
  }
}

export {};
