import { FormEvent, useState } from "react";

export default function LiftingPrintModal({
  open,
  defaultAccount,
  onClose,
  onPrint,
}: {
  open: boolean;
  defaultAccount: string;
  onClose(): void;
  onPrint(payload: {
    party_name: string;
    from_challan: number;
    to_challan: number;
    save_pdf: boolean;
    copy_label: string;
  }): Promise<{ count?: number; pdf_paths?: string[]; error?: string }>;
}) {
  const [partyName, setPartyName] = useState(defaultAccount);
  const [fromChallan, setFromChallan] = useState("1");
  const [toChallan, setToChallan] = useState("1");
  const [savePdf, setSavePdf] = useState(true);
  const [showOnScreen, setShowOnScreen] = useState(true);
  const [copy, setCopy] = useState<"original" | "duplicate" | "triplicate">("original");
  const [progress, setProgress] = useState("");
  const [paths, setPaths] = useState<string[]>([]);

  if (!open) return null;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setProgress("Printing…");
    const result = await onPrint({
      party_name: partyName,
      from_challan: Number(fromChallan) || 1,
      to_challan: Number(toChallan) || 1,
      save_pdf: savePdf,
      copy_label: copy,
    });
    if (result.error) {
      setProgress(result.error);
      return;
    }
    setPaths(result.pdf_paths ?? []);
    setProgress(`Progress : 100 % · Total PDFs Created : ${result.count ?? 0}`);
  }

  return (
    <div className="lifting-modal-overlay" role="presentation">
      <form className="lifting-print-modal" role="dialog" aria-label="Lifting print" onSubmit={(e) => void submit(e)}>
        <h2>Lifting Print</h2>
        <label>
          Enter A/c Name
          <input value={partyName} onChange={(event) => setPartyName(event.target.value)} />
        </label>
        <div className="lifting-print-range">
          <label>
            From Chln No.
            <input value={fromChallan} onChange={(event) => setFromChallan(event.target.value)} />
          </label>
          <label>
            To Chln No.
            <input value={toChallan} onChange={(event) => setToChallan(event.target.value)} />
          </label>
        </div>
        <div className="lifting-print-options">
          <label>
            <input checked={savePdf} type="checkbox" onChange={(event) => setSavePdf(event.target.checked)} />
            Save PDF as Print
          </label>
          <label>
            <input
              checked={showOnScreen}
              type="checkbox"
              onChange={(event) => setShowOnScreen(event.target.checked)}
            />
            Show On Screen Only
          </label>
          <label>
            <input
              checked={copy === "original"}
              name="copy"
              type="radio"
              onChange={() => setCopy("original")}
            />
            Original
          </label>
          <label>
            <input
              checked={copy === "duplicate"}
              name="copy"
              type="radio"
              onChange={() => setCopy("duplicate")}
            />
            Duplicate
          </label>
          <label>
            <input
              checked={copy === "triplicate"}
              name="copy"
              type="radio"
              onChange={() => setCopy("triplicate")}
            />
            Triplicate
          </label>
        </div>
        <div className="lifting-print-actions">
          <button type="submit">Print</button>
          <button type="button" onClick={onClose}>
            Cancel
          </button>
        </div>
        {progress && <p className="lifting-print-progress">{progress}</p>}
        {paths.length > 0 && <p className="lifting-print-progress">{paths.join("; ")}</p>}
      </form>
    </div>
  );
}
