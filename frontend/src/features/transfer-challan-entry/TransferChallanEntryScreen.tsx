import LegacyFormContainer from "../shared/LegacyFormContainer";

export default function TransferChallanEntryScreen({ onExit }: { onExit(): void }) {
  return (
    <LegacyFormContainer
      title="Transfer Challan"
      migrationNote="Phase 2: migrate DenseDocumentForm Transfer Challan config."
      onExit={onExit}
      saveOnF12
    >
      <p className="accounts-entry-error">Scaffold — use Daily menu until cutover.</p>
    </LegacyFormContainer>
  );
}
