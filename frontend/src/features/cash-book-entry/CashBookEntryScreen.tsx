import LegacyFormContainer from "../shared/LegacyFormContainer";

export default function CashBookEntryScreen({ onExit }: { onExit(): void }) {
  return (
    <LegacyFormContainer
      title="Cash Book"
      migrationNote="Phase 2: migrate CashBookForm from EntryWindowImpl."
      onExit={onExit}
    >
      <p className="accounts-entry-error">Scaffold — use Daily → Cash Book until cutover.</p>
    </LegacyFormContainer>
  );
}
