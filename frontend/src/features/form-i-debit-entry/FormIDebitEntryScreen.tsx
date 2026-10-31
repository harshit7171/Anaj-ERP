import LegacyFormContainer from "../shared/LegacyFormContainer";

export default function FormIDebitEntryScreen({
  variant,
  onExit,
}: {
  variant: "form_i_debit" | "sale_invoice";
  onExit(): void;
}) {
  const title = variant === "form_i_debit" ? "Form - I (Dr.)" : "Sale Invoice";
  return (
    <LegacyFormContainer
      title={title}
      migrationNote="Phase 2: migrate SaleBill from EntryWindowImpl."
      onExit={onExit}
    >
      <p className="accounts-entry-error">Scaffold — use Daily menu until cutover.</p>
    </LegacyFormContainer>
  );
}
