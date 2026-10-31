export type MandiFieldIssue = {
  field: string;
  message: string;
};

export function validateDenseDocument(input: {
  partyLabel?: string;
  hasParty: boolean;
  lineCount: number;
  hasCommodityLine: boolean;
  documentNumber: string;
}): MandiFieldIssue[] {
  const issues: MandiFieldIssue[] = [];
  if (!input.documentNumber.trim()) {
    issues.push({ field: "document_number", message: "Bill / document number is required." });
  }
  if (input.partyLabel && !input.hasParty) {
    issues.push({ field: "party", message: `${input.partyLabel} is required.` });
  }
  if (!input.hasCommodityLine || input.lineCount === 0) {
    issues.push({
      field: "commodity",
      message: "Add at least one commodity row with bags, weight, and rate.",
    });
  }
  return issues;
}
