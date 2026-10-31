export type ApiResult = { ok: boolean; error?: string };

export type AccountMasterApi = {
  save_account_master?(payload: Record<string, unknown>): Promise<ApiResult>;
  get_party_master?(partyId: string): Promise<ApiResult & { party?: Record<string, unknown> }>;
  get_account_master?(accountId: string): Promise<ApiResult & { party?: Record<string, unknown> }>;
  delete_account_master?(accountId: string): Promise<ApiResult>;
  lookup_gstin?(gstin: string): Promise<ApiResult & { taxpayer?: Record<string, string> }>;
  find_accounts?(query?: string, city?: string, party_type?: string): Promise<
    ApiResult & { rows?: Record<string, unknown>[] }
  >;
};

export type FormState = Record<string, string>;
