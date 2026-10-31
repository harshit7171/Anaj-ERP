/** Shared helpers for mandi document posting (Form-J, Form-I, dense forms). */

export function rupeesToPaise(value: string): number {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return 0;
  return Math.round(amount * 100);
}

export function buildChargeOverrides(
  calculation: Record<string, unknown> | null,
  rates: Record<string, string>,
): Record<string, { amount_paise: number; reason: string }> {
  const charges = (calculation?.charges ?? []) as Record<string, unknown>[];
  return Object.fromEntries(
    charges.flatMap((charge) => {
      const code = String(charge.code);
      const entered = rates[code];
      const original = Number(charge.rate_decimal);
      if (entered === undefined || Number(entered) === original || original === 0) return [];
      const automatic = Math.abs(Number(charge.automatic_amount_paise));
      return [
        [
          code,
          {
            amount_paise: Math.round((automatic * Number(entered || 0)) / original),
            reason: "Operator adjusted rate before posting",
          },
        ],
      ];
    }),
  );
}

export type DocumentWorkflowResult = {
  ok: boolean;
  error?: string;
  document?: Record<string, unknown>;
  calculation?: Record<string, unknown>;
  document_number?: string;
};

export type DocumentWorkflowApi = {
  calculate_document(payload: Record<string, unknown>): Promise<DocumentWorkflowResult>;
  post_document(payload: Record<string, unknown>): Promise<DocumentWorkflowResult>;
  next_document_number(documentType: string): Promise<DocumentWorkflowResult>;
  print_document(documentId: string): Promise<DocumentWorkflowResult>;
  print_mandi_bill?(payload: Record<string, unknown>): Promise<DocumentWorkflowResult>;
  preview_mandi_statutory_html?(payload: Record<string, unknown>): Promise<
    DocumentWorkflowResult & { path?: string }
  >;
};

export function documentWorkflowApi(): DocumentWorkflowApi | undefined {
  return window.pywebview?.api as unknown as DocumentWorkflowApi | undefined;
}
