import { useEffect, useState } from "react";

export function EntryFormMessage({
  result,
}: {
  result: { ok: boolean; error?: string; error_type?: string } | null;
}) {
  const [dismissed, setDismissed] = useState(false);
  useEffect(() => setDismissed(false), [result]);
  if (!result) return null;
  if (
    !result.ok
    && !dismissed
    && ["ClockTamperException", "LicenseWriteLockedError"].includes(result.error_type ?? "")
  ) {
    const tamper = result.error_type === "ClockTamperException";
    return (
      <div className="blocking-modal license-blocker" role="alertdialog" aria-modal="true">
        <div className="saved-dialog">
          <header><span>Anaj Accounting ERP</span></header>
          <p>{result.error}</p>
          {!tamper && <button type="button" onClick={() => setDismissed(true)}>Close</button>}
        </div>
      </div>
    );
  }
  return (
    <p className={result.ok ? "success-message accounts-entry-status" : "error-message accounts-entry-error"}>
      {result.ok ? "Saved successfully." : result.error}
    </p>
  );
}

export function EntrySavedModal({ onClose }: { onClose(): void }) {
  return (
    <div className="blocking-modal" role="dialog" aria-modal="true" aria-labelledby="saved-title">
      <div className="saved-dialog">
        <header>
          <span id="saved-title">Anaj Accounting ERP</span>
          <button aria-label="Close" type="button" onClick={onClose}>×</button>
        </header>
        <p>Data has been Successfully Saved</p>
        <button autoFocus type="button" onClick={onClose}>Close</button>
      </div>
    </div>
  );
}
