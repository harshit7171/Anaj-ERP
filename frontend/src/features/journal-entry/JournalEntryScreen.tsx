import LegacyFormContainer from "../shared/LegacyFormContainer";

export default function JournalEntryScreen({
  kind,
  onExit,
}: {
  kind: "Journal" | "Accounting Voucher";
  onExit(): void;
}) {
  return (
    <LegacyFormContainer
      title={kind}
      migrationNote="Phase 2: migrate JournalForm from EntryWindowImpl (distinct from voucher-entry menu)."
      onExit={onExit}
      saveOnF12
    >
      <p className="accounts-entry-error">Scaffold — use Daily → Journal until cutover.</p>
    </LegacyFormContainer>
  );
}
