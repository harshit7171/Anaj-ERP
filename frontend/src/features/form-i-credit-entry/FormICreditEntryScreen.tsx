import LegacyFormContainer from "../shared/LegacyFormContainer";

export default function FormICreditEntryScreen({ onExit }: { onExit(): void }) {
  return (
    <LegacyFormContainer
      title="Form - I (Cr.)"
      migrationNote="Phase 2: migrate FormICredit from EntryWindowImpl."
      onExit={onExit}
    >
      <p className="accounts-entry-error">Scaffold — use Daily menu until cutover.</p>
    </LegacyFormContainer>
  );
}
