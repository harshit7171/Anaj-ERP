import LegacyFormContainer from "../shared/LegacyFormContainer";

/** Phase 2: wrap DenseDocumentForm configs Inward / Outward / Gate Pass. */
export default function GatePassEntryScreen({
  screen,
  onExit,
}: {
  screen: "Inward" | "Outward" | "Gate Pass";
  onExit(): void;
}) {
  return (
    <LegacyFormContainer
      title={screen}
      migrationNote="Phase 2: move DenseDocumentForm gate/weighbridge configs here (weighbridge slip header field)."
      onExit={onExit}
      saveOnF12
    >
      <p className="accounts-entry-error">
        Scaffold — use Daily → {screen} (dense form) until cutover.
      </p>
    </LegacyFormContainer>
  );
}
