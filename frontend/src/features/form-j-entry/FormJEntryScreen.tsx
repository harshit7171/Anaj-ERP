import Autocomplete from "../../Autocomplete";
import { useGridEnterNavigation } from "../../hooks/useGridEnterNavigation";
import { EntryFormMessage, EntrySavedModal } from "../shared/EntryFormFeedback";
import LegacyFormContainer from "../shared/LegacyFormContainer";
import { useFormJEntry } from "./useFormJEntry";

export default function FormJEntryScreen({ onExit }: { onExit(): void }) {
  const vm = useFormJEntry({ onExit });
  const handleGridEnter = useGridEnterNavigation(vm.appendDheri);

  return (
    <>
      <LegacyFormContainer
        title="Form - J"
        saveOnF12
        onSave={() => void vm.submit()}
        onView={() => void vm.calculate()}
        onPrint={vm.postedId ? () => void vm.printDocument() : undefined}
        onExit={onExit}
        status={<EntryFormMessage result={vm.result} />}
      >
        <div className="transaction-body has-sidebar" onKeyDown={handleGridEnter}>
          <section className="transaction-grid-panel">
            <div className="transaction-header-grid mb-2">
              <div className="min-w-[220px]">
                <Autocomplete
                  autoFocus
                  entityType="party"
                  label="Farmer's Name"
                  required
                  value={vm.farmer}
                  onSelect={vm.setFarmer}
                />
              </div>
              <label className="inline-flex min-h-8 items-center gap-2 text-xs font-semibold">
                No.
                <input
                  required
                  className="picker-field"
                  value={vm.number}
                  onChange={(event) => vm.setNumber(event.target.value)}
                />
              </label>
              <label className="inline-flex min-h-8 items-center gap-2 text-xs font-semibold">
                Date
                <input
                  type="date"
                  className="picker-field"
                  value={vm.date}
                  onChange={(event) => vm.setDate(event.target.value)}
                />
              </label>
              <label className="inline-flex min-h-8 items-center gap-2 text-xs font-semibold">
                Due Date
                <input
                  type="date"
                  className="picker-field"
                  value={vm.dueDate}
                  onChange={(event) => vm.setDueDate(event.target.value)}
                />
              </label>
            </div>
            <section className="dheri-panel">
              <h3 className="mb-1 font-semibold">Dheri Details</h3>
              <div className="dheri-grid dheri-grid-header">
                <span>Item</span>
                <span>Purchaser</span>
                <span>GP No.</span>
                <span>Bag</span>
                <span>Pack</span>
                <span>Extra</span>
                <span>Qty</span>
                <span>Rate</span>
                <span>Amount</span>
                <span />
              </div>
              {vm.rows.map((row) => {
                const quantity = vm.formJQuantity(row);
                const amount = quantity * Number(row.rate || 0);
                return (
                  <div className="dheri-grid" data-grid-row key={row.rowId}>
                    <Autocomplete
                      entityType="commodity"
                      label=""
                      value={row.commodity}
                      onSelect={(value) => vm.updateRow(row.rowId, { commodity: value })}
                    />
                    <Autocomplete
                      entityType="party"
                      label=""
                      value={row.purchaser}
                      onSelect={(value) => vm.updateRow(row.rowId, { purchaser: value })}
                    />
                    <input value={row.gpNo} onChange={(event) => vm.updateRow(row.rowId, { gpNo: event.target.value })} />
                    <input
                      type="number"
                      min="0"
                      step="1"
                      inputMode="numeric"
                      value={row.bags}
                      onChange={(event) => vm.updateRow(row.rowId, { bags: event.target.value })}
                    />
                    <input
                      inputMode="decimal"
                      value={row.pack}
                      onChange={(event) => vm.updateRow(row.rowId, { pack: event.target.value })}
                    />
                    <input
                      inputMode="decimal"
                      value={row.extra}
                      onChange={(event) => vm.updateRow(row.rowId, { extra: event.target.value })}
                    />
                    <output>{quantity.toFixed(3)}</output>
                    <input
                      inputMode="decimal"
                      value={row.rate}
                      onChange={(event) => vm.updateRow(row.rowId, { rate: event.target.value })}
                    />
                    <output>{amount.toFixed(2)}</output>
                    <button
                      aria-label="Remove dheri"
                      disabled={vm.rows.length === 1}
                      type="button"
                      onClick={() => vm.setRows((current) => current.filter((item) => item.rowId !== row.rowId))}
                    >
                      ×
                    </button>
                  </div>
                );
              })}
              <button className="add-dheri mt-1" type="button" onClick={vm.appendDheri}>
                Add Dheri
              </button>
            </section>
          </section>
          <aside className="transaction-summary-panel expense-panel">
            <h3 className="mb-1 font-semibold">Expenses Details</h3>
            {vm.showExpenses && (
              <div className="expense-list">
                <div className="expense-list-header">
                  <span />
                  <span>Expense</span>
                  <span>% / Unit</span>
                  <span>Amount</span>
                </div>
                {vm.charges
                  .filter((charge) => charge.code !== "BONUS")
                  .map((charge) => (
                    <label key={String(charge.code)}>
                      <input
                        type="checkbox"
                        checked={!vm.excludedCharges.includes(String(charge.code))}
                        onChange={(event) =>
                          vm.setExcludedCharges((codes) =>
                            event.target.checked
                              ? codes.filter((code) => code !== String(charge.code))
                              : [...codes, String(charge.code)],
                          )
                        }
                      />
                      <span>{String(charge.label)}</span>
                      <input
                        aria-label={`${String(charge.label)} rate`}
                        value={vm.rateOverrides[String(charge.code)] ?? String(charge.rate_decimal)}
                        onChange={(event) =>
                          vm.setRateOverrides((current) => ({
                            ...current,
                            [String(charge.code)]: event.target.value,
                          }))
                        }
                      />
                      <strong>₹{(Number(charge.final_amount_paise) / 100).toFixed(2)}</strong>
                    </label>
                  ))}
                {!vm.charges.length && <p>Add a complete dheri row to calculate expenses.</p>}
              </div>
            )}
            <div className="expense-actions">
              <button type="button" onClick={() => vm.setShowExpenses((value) => !value)}>
                Add / Remove Exp.
              </button>
              <button type="button" onClick={() => void vm.calculate()}>
                Refresh
              </button>
            </div>
            <div className="form-j-totals">
              <span>Total Amount</span>
              <output>₹{(Number(vm.calculation?.subtotal_paise ?? 0) / 100).toFixed(2)}</output>
              <span>Total Expenses</span>
              <output>₹{(Math.abs(Number(vm.calculation?.total_charges_paise ?? 0)) / 100).toFixed(2)}</output>
              <label>Bonus</label>
              <input type="number" min="0" step="0.01" value={vm.bonus} onChange={(event) => vm.setBonus(event.target.value)} />
              <strong>NET AMOUNT</strong>
              <output>₹{(Number(vm.calculation?.grand_total_paise ?? 0) / 100).toFixed(2)}</output>
            </div>
            <div className="mt-3 space-y-2">
              <Autocomplete entityType="account" label="Purchase Account" value={vm.purchaseAccount} onSelect={vm.setPurchaseAccount} />
              <Autocomplete entityType="account" label="Farmer Account" value={vm.farmerAccount} onSelect={vm.setFarmerAccount} />
              <Autocomplete
                entityType="account"
                label="Commodity Transfer A/c"
                value={vm.commodityTransfer}
                onSelect={vm.setCommodityTransfer}
              />
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={vm.gatePassRequired}
                  onChange={(event) => vm.setGatePassRequired(event.target.checked)}
                />{" "}
                Gate Pass No.
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={vm.selfPurchase}
                  onChange={(event) => vm.setSelfPurchase(event.target.checked)}
                />{" "}
                Self Purchase
              </label>
            </div>
          </aside>
        </div>
      </LegacyFormContainer>
      {vm.showSavedModal && <EntrySavedModal onClose={() => vm.setShowSavedModal(false)} />}
    </>
  );
}
