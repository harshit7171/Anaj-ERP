import { FormEvent, useRef } from "react";

import DeleteConfirmModal from "../../components/DeleteConfirmModal";
import { useFormEnterFlow } from "../../hooks/useFormEnterFlow";
import { useGridEnterNavigation } from "../../hooks/useGridEnterNavigation";
import LiftingExpenseModal from "../lifting-entry/LiftingExpenseModal";
import { useMandiPurchase } from "./useMandiPurchase";

export default function MandiPurchaseEntryScreen({
  mode,
  onExit,
}: {
  mode: "add" | "modify";
  onExit(): void;
}) {
  const m = useMandiPurchase({ mode, onExit });
  const formRef = useRef<HTMLFormElement>(null);
  useFormEnterFlow(formRef, true);

  const handleGridEnter = useGridEnterNavigation(() => {
    m.appendBlankLine();
    return false;
  });

  return (
    <>
      <form
        ref={formRef}
        className="mandi-purchase-screen"
        data-mandi-purchase-form
        onSubmit={(event: FormEvent) => void m.save(event)}
      >
        <header className="mandi-purchase-title">{m.screenTitle}</header>
        <div className="mandi-purchase-toolbar">
          <button type="submit">Save (F3)</button>
          <button type="button" onClick={onExit}>
            Cancel (F4)
          </button>
          {mode === "modify" && (
            <>
              <button type="button" onClick={() => void m.runFind()}>
                Find (F5)
              </button>
              <button disabled={!m.documentId} type="button" onClick={() => m.setDeleteOpen(true)}>
                Delete (F6)
              </button>
              <label className="mandi-purchase-find-bill">
                Bill No
                <input value={m.searchBillNo} onChange={(event) => m.setSearchBillNo(event.target.value)} />
              </label>
            </>
          )}
          <button type="button" onClick={() => m.setExpenseOpen(true)}>
            Expenses
          </button>
          <button className="mandi-purchase-recalc" type="button" onClick={m.recalculateAll}>
            Recalculate
          </button>
          <span className="mandi-purchase-user">User {m.userName}</span>
        </div>
        <div className="mandi-purchase-header">
          <div className="mandi-purchase-header-left">
            <label>
              Date
              <input
                type={mode === "add" ? "date" : "text"}
                value={m.entryDate}
                onChange={(event) => m.setEntryDate(event.target.value)}
              />
            </label>
            <span className="mandi-purchase-weekday">{m.weekday}</span>
            <label>
              Cash/Credit
              <select value={m.cashCredit} onChange={(event) => m.setCashCredit(event.target.value)}>
                <option value="Credit">Credit</option>
                <option value="Cash">Cash</option>
              </select>
            </label>
            <label>
              Purchase A/c
              <input
                value={m.purchasePartyName}
                onChange={(event) => m.setPurchasePartyName(event.target.value)}
                onFocus={() => void m.openPicker("purchase_ac", -1, m.purchasePartyName)}
              />
            </label>
            <label>
              Mandi (City)
              <input value={m.mandiCity} onChange={(event) => m.setMandiCity(event.target.value)} />
            </label>
            <label>
              Exp Master
              <input value={m.expMaster} onChange={(event) => m.setExpMaster(event.target.value)} />
            </label>
            <label>
              Broker
              <input value={m.broker} onChange={(event) => m.setBroker(event.target.value)} />
            </label>
            <div className="mandi-purchase-flags">
              <label>
                Market Paid
                <select value={m.marketPaid} onChange={(event) => m.setMarketPaid(event.target.value)}>
                  <option value="N">N</option>
                  <option value="Y">Y</option>
                </select>
              </label>
              <label>
                Pur Type
                <select value={m.purType} onChange={(event) => m.setPurType(event.target.value)}>
                  <option value="L">L</option>
                  <option value="P">P</option>
                </select>
              </label>
              <label>
                RCM (Y/N)
                <select value={m.rcm} onChange={(event) => m.setRcm(event.target.value)}>
                  <option value="N">N</option>
                  <option value="Y">Y</option>
                </select>
              </label>
              <label>
                GST (Y/N)
                <select value={m.gst} onChange={(event) => m.setGst(event.target.value)}>
                  <option value="N">N</option>
                  <option value="Y">Y</option>
                </select>
              </label>
            </div>
            <label>
              Amount
              <input readOnly className="mandi-purchase-amount" value={m.totals.total_amount} />
            </label>
            <label>
              Due Date
              <input value={m.dueDate} onChange={(event) => m.setDueDate(event.target.value)} />
            </label>
            <label>
              Stock Rcvd.
              <select value={m.stockRcvd} onChange={(event) => m.setStockRcvd(event.target.value)}>
                <option value="N">N</option>
                <option value="Y">Y</option>
              </select>
            </label>
            <label>
              TDS Rate
              <input value={m.tdsRate} onChange={(event) => m.setTdsRate(event.target.value)} />
            </label>
            <label>
              Entry No
              <input value={m.documentNumber} onChange={(event) => m.setDocumentNumber(event.target.value)} />
            </label>
            <label className="mandi-purchase-remarks">
              Remarks
              <input value={m.remarks} onChange={(event) => m.setRemarks(event.target.value)} />
            </label>
          </div>
          <div className="mandi-purchase-summary-panel">
            <table>
              <thead>
                <tr>
                  <th>Item Name</th>
                  <th>Nugs</th>
                  <th>Weight</th>
                  <th>Amount</th>
                  <th>Avg. Rate</th>
                </tr>
              </thead>
              <tbody>
                {m.itemSummary.map((row) => (
                  <tr key={row.item_name}>
                    <td>{row.item_name}</td>
                    <td>{row.nugs}</td>
                    <td>{row.weight}</td>
                    <td>{row.amount}</td>
                    <td>{row.avg_rate}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="mandi-purchase-tabs">
          <button
            className={m.activeTab === "items" ? "active items" : "items"}
            type="button"
            onClick={() => m.setActiveTab("items")}
          >
            Items
          </button>
          <button
            className={m.activeTab === "transport" ? "active transport" : "transport"}
            type="button"
            onClick={() => m.setActiveTab("transport")}
          >
            Transport
          </button>
          <button
            className={m.activeTab === "bardana" ? "active bardana" : "bardana"}
            type="button"
            onClick={() => m.setActiveTab("bardana")}
          >
            Bardana
          </button>
        </div>
        {m.activeTab === "items" && (
          <div className="mandi-purchase-grid-wrap" onKeyDown={handleGridEnter}>
            <table className="mandi-purchase-grid">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Party</th>
                  <th>Bill No</th>
                  <th>Due Date</th>
                  <th>Item</th>
                  <th>Unit</th>
                  <th>Nugs/Bags</th>
                  <th>Weight</th>
                  <th>N/W</th>
                  <th>Rate</th>
                  <th>Amount</th>
                  <th>ROff</th>
                  <th>Bill Amt</th>
                  <th>TdsOn</th>
                  <th>Tds%</th>
                  <th>TdsOn</th>
                  <th>Tds</th>
                </tr>
              </thead>
              <tbody>
                {m.lines.map((line, index) => (
                  <tr key={`mandi-${index}`} data-grid-row>
                    <td>{index + 1}</td>
                    <td>
                      <input
                        value={line.party_name}
                        onChange={(event) => m.updateLine(index, { party_name: event.target.value })}
                        onFocus={() => void m.openPicker("party", index)}
                      />
                    </td>
                    <td>
                      <input
                        value={line.bill_no}
                        onChange={(event) => m.updateLine(index, { bill_no: event.target.value })}
                      />
                    </td>
                    <td>
                      <input
                        value={line.due_date}
                        onChange={(event) => m.updateLine(index, { due_date: event.target.value })}
                      />
                    </td>
                    <td>
                      <input
                        value={line.item_name}
                        onChange={(event) => m.updateLine(index, { item_name: event.target.value })}
                        onFocus={() => void m.openPicker("item", index)}
                      />
                    </td>
                    <td>
                      <input value={line.unit} onChange={(event) => m.updateLine(index, { unit: event.target.value })} />
                    </td>
                    <td>
                      <input value={line.nugs} onChange={(event) => m.updateLine(index, { nugs: event.target.value })} />
                    </td>
                    <td>
                      <input
                        value={line.weight}
                        onChange={(event) => m.updateLine(index, { weight: event.target.value })}
                      />
                    </td>
                    <td>
                      <select value={line.nw} onChange={(event) => m.updateLine(index, { nw: event.target.value })}>
                        <option value="N">N</option>
                        <option value="Y">Y</option>
                      </select>
                    </td>
                    <td>
                      <input
                        value={line.rate}
                        onChange={(event) => m.updateLine(index, { rate: event.target.value })}
                        onFocus={() => void m.openPicker("rate", index)}
                      />
                    </td>
                    <td>
                      <input readOnly value={line.amount} />
                    </td>
                    <td>
                      <select value={line.r_off} onChange={(event) => m.updateLine(index, { r_off: event.target.value })}>
                        <option value="Y">Y</option>
                        <option value="N">N</option>
                      </select>
                    </td>
                    <td>
                      <input readOnly value={line.bill_amt} />
                    </td>
                    <td>
                      <select
                        value={line.tds_on}
                        onChange={(event) => m.updateLine(index, { tds_on: event.target.value })}
                      >
                        <option value="N">N</option>
                        <option value="Y">Y</option>
                      </select>
                    </td>
                    <td>
                      <input
                        value={line.tds_pct}
                        onChange={(event) => m.updateLine(index, { tds_pct: event.target.value })}
                      />
                    </td>
                    <td>
                      <input readOnly value={line.tds_on_amt} />
                    </td>
                    <td>
                      <input readOnly value={line.tds} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {m.activeTab === "transport" && (
          <div className="mandi-purchase-tab-panel">
            <label>
              Transporter
              <input
                value={m.transport.transporter}
                onChange={(event) => m.setTransport((prev) => ({ ...prev, transporter: event.target.value }))}
              />
            </label>
            <label>
              Vehicle No
              <input
                value={m.transport.vehicle_no}
                onChange={(event) => m.setTransport((prev) => ({ ...prev, vehicle_no: event.target.value }))}
              />
            </label>
            <label>
              Freight
              <input
                value={m.transport.freight}
                onChange={(event) => m.setTransport((prev) => ({ ...prev, freight: event.target.value }))}
              />
            </label>
            <label>
              Remarks
              <input
                value={m.transport.remarks}
                onChange={(event) => m.setTransport((prev) => ({ ...prev, remarks: event.target.value }))}
              />
            </label>
          </div>
        )}
        {m.activeTab === "bardana" && (
          <div className="mandi-purchase-tab-panel">
            <label>
              Bardana Type
              <select
                value={m.bardana.bardana_type}
                onChange={(event) => m.setBardana((prev) => ({ ...prev, bardana_type: event.target.value }))}
              >
                <option value="Jute">Jute</option>
                <option value="Plastic">Plastic</option>
                <option value="HDPE">HDPE</option>
              </select>
            </label>
            <label>
              Bags
              <input
                value={m.bardana.bags}
                onChange={(event) => m.setBardana((prev) => ({ ...prev, bags: event.target.value }))}
              />
            </label>
            <label>
              Remarks
              <input
                value={m.bardana.remarks}
                onChange={(event) => m.setBardana((prev) => ({ ...prev, remarks: event.target.value }))}
              />
            </label>
          </div>
        )}
        {(m.status || m.error) && (
          <p className={`mandi-purchase-status${m.error ? " mandi-purchase-error" : ""}`}>{m.error || m.status}</p>
        )}
      </form>
      {m.picker && (
        <div className="mandi-picker" role="listbox">
          <ul>
            {m.picker.rows.map((row, index) => (
              <li key={`pick-${index}`}>
                <button type="button" onClick={() => m.applyPicker(row)}>
                  {m.picker!.kind === "purchase_ac" || m.picker!.kind === "party"
                    ? String(row.name ?? "")
                    : m.picker!.kind === "item"
                      ? String(row.item_name ?? "")
                      : `${String(row.rate ?? "")} · ${String(row.weight ?? "")}`}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      <LiftingExpenseModal
        open={m.expenseOpen}
        onAmt={m.totals.total_amount}
        onClose={() => m.setExpenseOpen(false)}
        onQty={m.totals.total_nugs}
        onSave={m.setExpenses}
        onWt={m.totals.total_weight}
        rows={m.expenses}
        title={`Purchase Expenses (${m.purchasePartyName || "Purchase"})`}
      />
      <DeleteConfirmModal
        open={m.deleteOpen}
        recordLabel={m.documentNumber}
        onCancel={() => m.setDeleteOpen(false)}
        onConfirm={() => void m.confirmDelete()}
      />
    </>
  );
}
