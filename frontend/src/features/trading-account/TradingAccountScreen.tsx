import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import DeleteConfirmModal from "../../components/DeleteConfirmModal";
import { useFormEnterFlow } from "../../hooks/useFormEnterFlow";
import useFieldFocusHandlers from "../../hooks/useFieldFocusHandlers";

type ApiResult = { ok: boolean; error?: string };

type TradingApi = {
  list_items?(): Promise<ApiResult & { items?: Record<string, unknown>[] }>;
  list_trading_accounts?(): Promise<
    ApiResult & { trading_accounts?: Record<string, unknown>[] }
  >;
  get_trading_account?(id: string): Promise<
    ApiResult & { trading_account?: Record<string, unknown> }
  >;
  save_trading_account?(payload: Record<string, unknown>): Promise<ApiResult>;
  delete_trading_account?(id: string): Promise<ApiResult>;
};

function api(): TradingApi | undefined {
  return window.pywebview?.api as unknown as TradingApi | undefined;
}

function itemLabel(row: Record<string, unknown>): string {
  const name = String(row.name ?? "");
  const variety = String(row.variety ?? "").trim();
  return variety ? `${name} ${variety}`.trim() : name;
}

type ItemSide = "raw" | "finished";

export default function TradingAccountScreen({
  mode,
  onExit,
}: {
  mode: "add" | "modify";
  onExit(): void;
}) {
  const formRef = useRef<HTMLFormElement>(null);
  const title = mode === "add" ? "Trading Account Add" : "Trading Account Modify";

  const [tradingAccountId, setTradingAccountId] = useState("");
  const [tradingCode, setTradingCode] = useState("");
  const [accountName, setAccountName] = useState("");
  const [profitLossAccount, setProfitLossAccount] = useState("");
  const [activeSide, setActiveSide] = useState<ItemSide>("raw");
  const [rawSearch, setRawSearch] = useState("");
  const [finishedSearch, setFinishedSearch] = useState("");
  const [rawSelected, setRawSelected] = useState<Set<string>>(new Set());
  const [finishedSelected, setFinishedSelected] = useState<Set<string>>(new Set());
  const [allItems, setAllItems] = useState<Record<string, unknown>[]>([]);

  const [loaded, setLoaded] = useState(mode !== "modify");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [findOpen, setFindOpen] = useState(false);
  const [findQuery, setFindQuery] = useState("");
  const [findRows, setFindRows] = useState<Record<string, unknown>[]>([]);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const fieldsLocked = mode === "modify" && !loaded;

  useFormEnterFlow(formRef, true);
  useFieldFocusHandlers(formRef, true);

  useEffect(() => {
    void api()?.list_items?.().then((response) => {
      if (response?.ok && response.items) {
        setAllItems(response.items);
      }
    });
  }, []);

  useEffect(() => {
    setTradingAccountId("");
    setTradingCode("");
    setAccountName("");
    setProfitLossAccount("");
    setRawSelected(new Set());
    setFinishedSelected(new Set());
    setRawSearch("");
    setFinishedSearch("");
    setActiveSide("raw");
    setLoaded(mode !== "modify");
    setError("");
    setStatus("");
    if (mode === "modify") {
      setFindOpen(true);
      void refreshFindList("");
    } else {
      void suggestNextCode();
    }
  }, [mode]);

  async function suggestNextCode() {
    const response = await api()?.list_trading_accounts?.();
    if (!response?.ok || !response.trading_accounts?.length) {
      setTradingCode("1");
      return;
    }
    const codes = response.trading_accounts
      .map((row) => Number(String(row.trading_code ?? "").replace(/\D/g, "")))
      .filter((n) => Number.isFinite(n) && n > 0);
    const next = codes.length ? Math.max(...codes) + 1 : 1;
    setTradingCode(String(next));
  }

  async function refreshFindList(query: string) {
    const response = await api()?.list_trading_accounts?.();
    if (!response?.ok) {
      setFindRows([]);
      return;
    }
    const q = query.trim().toLowerCase();
    const rows = (response.trading_accounts ?? []).filter((row) => {
      if (!q) return true;
      const hay = [row.trading_code, row.name, row.profit_loss_account, row.trading_account_id]
        .map((v) => String(v ?? "").toLowerCase())
        .join(" ");
      return hay.includes(q);
    });
    setFindRows(rows);
  }

  function applyRecord(row: Record<string, unknown>) {
    setTradingAccountId(String(row.trading_account_id ?? ""));
    setTradingCode(String(row.trading_code ?? ""));
    setAccountName(String(row.name ?? ""));
    setProfitLossAccount(String(row.profit_loss_account ?? ""));
    const raw = row.raw_commodity_ids;
    const finished = row.finished_commodity_ids;
    setRawSelected(new Set(Array.isArray(raw) ? raw.map(String) : []));
    setFinishedSelected(new Set(Array.isArray(finished) ? finished.map(String) : []));
    setLoaded(true);
    setFindOpen(false);
    setStatus("Trading account loaded — you can edit and save (F3).");
    setError("");
  }

  async function runFind(searchText?: string) {
    const bridge = api();
    if (!bridge) {
      setError("Desktop API is not available.");
      return;
    }
    const query = (searchText ?? tradingCode ?? findQuery).trim();
    if (mode === "modify" && query && !findOpen) {
      const detail = await bridge.get_trading_account?.(query);
      if (detail?.ok && detail.trading_account) {
        applyRecord(detail.trading_account);
        return;
      }
    }
    await refreshFindList(query);
    setFindQuery(query);
    setFindOpen(true);
  }

  function toggleItem(side: ItemSide, commodityId: string, checked: boolean) {
    const setter = side === "raw" ? setRawSelected : setFinishedSelected;
    setter((prev) => {
      const next = new Set(prev);
      if (checked) {
        next.add(commodityId);
      } else {
        next.delete(commodityId);
      }
      return next;
    });
  }

  const filteredRaw = useMemo(() => {
    const q = rawSearch.trim().toLowerCase();
    return allItems.filter((row) => {
      if (!q) return true;
      return itemLabel(row).toLowerCase().includes(q);
    });
  }, [allItems, rawSearch]);

  const filteredFinished = useMemo(() => {
    const q = finishedSearch.trim().toLowerCase();
    return allItems.filter((row) => {
      if (!q) return true;
      return itemLabel(row).toLowerCase().includes(q);
    });
  }, [allItems, finishedSearch]);

  async function save(event: FormEvent) {
    event.preventDefault();
    setError("");
    const bridge = api();
    if (!bridge?.save_trading_account) {
      setError("Desktop API is not available.");
      return;
    }
    if (mode === "modify" && (!loaded || !tradingAccountId)) {
      setError("Select a trading account with Find (F5) before saving.");
      return;
    }
    if (!accountName.trim()) {
      setError("Trading account name is required.");
      return;
    }
    const payload: Record<string, unknown> = {
      name: accountName.trim(),
      trading_code: tradingCode.trim() || null,
      profit_loss_account: profitLossAccount.trim() || null,
      raw_commodity_ids: [...rawSelected],
      finished_commodity_ids: [...finishedSelected],
    };
    if (mode === "modify" && tradingAccountId) {
      payload.trading_account_id = tradingAccountId;
    }
    const response = await bridge.save_trading_account(payload);
    if (!response?.ok) {
      setError(response?.error ?? "Save failed.");
      return;
    }
    setStatus("Data has been Successfully Saved");
    if (mode === "add") {
      setAccountName("");
      setProfitLossAccount("");
      setRawSelected(new Set());
      setFinishedSelected(new Set());
      void suggestNextCode();
    }
  }

  async function confirmDelete() {
    const bridge = api();
    if (!bridge?.delete_trading_account || !tradingAccountId) {
      setError("Nothing to delete.");
      setDeleteOpen(false);
      return;
    }
    const response = await bridge.delete_trading_account(tradingAccountId);
    setDeleteOpen(false);
    if (!response?.ok) {
      setError(response?.error ?? "Delete failed.");
      return;
    }
    onExit();
  }

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "F3") {
        event.preventDefault();
        formRef.current?.requestSubmit();
      }
      if (event.key === "F4") {
        event.preventDefault();
        onExit();
      }
      if (event.key === "F5" && mode === "modify") {
        event.preventDefault();
        void runFind();
      }
      if (event.key === "F6" && mode === "modify" && loaded) {
        event.preventDefault();
        setDeleteOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  function renderItemList(
    side: ItemSide,
    rows: Record<string, unknown>[],
    selected: Set<string>,
    search: string,
    onSearch: (value: string) => void,
  ) {
    const isActive = activeSide === side;
    return (
      <div
        className={`trading-account-item-panel${isActive ? " trading-account-item-panel-active" : ""}`}
      >
        <label className="trading-account-radio">
          <input
            type="radio"
            name="item-side"
            checked={isActive}
            onChange={() => setActiveSide(side)}
          />
          {side === "raw" ? "Raw Materials" : "Finished Goods"}
        </label>
        <input
          className="trading-account-search"
          placeholder={
            side === "raw" ? "Search Raw Item Here" : "Search Finished Item Here"
          }
          value={search}
          onChange={(event) => onSearch(event.target.value)}
          onFocus={() => setActiveSide(side)}
        />
        <div className="trading-account-item-table-wrap">
          <table className="trading-account-item-table">
            <thead>
              <tr>
                <th aria-label="Select" />
                <th>Particulars</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const id = String(row.commodity_id ?? "");
                return (
                  <tr key={id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selected.has(id)}
                        disabled={fieldsLocked}
                        onChange={(event) =>
                          toggleItem(side, id, event.target.checked)
                        }
                      />
                    </td>
                    <td>{itemLabel(row)}</td>
                  </tr>
                );
              })}
              {!rows.length && (
                <tr>
                  <td colSpan={2}>No items found.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  return (
    <>
      <form
        ref={formRef}
        className="trading-account-screen"
        data-trading-account-form
        onSubmit={(event) => void save(event)}
      >
        <h2 className="trading-account-title">{title}</h2>

        {fieldsLocked && (
          <p className="trading-account-hint" role="status">
            Use <strong>Find (F5)</strong> to select a trading account. Fields stay read-only until
            one is loaded.
          </p>
        )}

        <fieldset className="trading-account-header" disabled={fieldsLocked}>
          <div className="trading-account-row trading-account-id-row">
            <span className="trading-account-label">Trading A/c. ID</span>
            <div className="trading-account-id-controls">
              <input
                className={`trading-account-input trading-account-id-input${mode === "add" ? " trading-account-input-readonly" : ""}`}
                data-enter-order={1}
                readOnly={mode === "add"}
                value={tradingCode}
                onChange={(event) => setTradingCode(event.target.value)}
              />
              {mode === "modify" && (
                <button className="trading-account-btn" type="button" onClick={() => void runFind()}>
                  Find (F5)
                </button>
              )}
            </div>
          </div>
          <div className="trading-account-row">
            <span className="trading-account-label">Trading A/c. Name</span>
            <input
              className="trading-account-input"
              data-enter-order={2}
              value={accountName}
              onChange={(event) => setAccountName(event.target.value)}
            />
          </div>
          <div className="trading-account-row">
            <span className="trading-account-label">Profit / Loss A/c.</span>
            <input
              className="trading-account-input"
              data-enter-order={3}
              value={profitLossAccount}
              onChange={(event) => setProfitLossAccount(event.target.value)}
            />
          </div>
        </fieldset>

        <div className="trading-account-actions trading-account-actions-top">
          {mode === "modify" && (
            <button
              className="trading-account-btn trading-account-btn-delete"
              disabled={!loaded}
              type="button"
              onClick={() => setDeleteOpen(true)}
            >
              Delete (F6)
            </button>
          )}
          <button
            className="trading-account-btn trading-account-btn-save"
            disabled={mode === "modify" && !loaded}
            type="submit"
          >
            Save (F3)
          </button>
          <button className="trading-account-btn" type="button" onClick={onExit}>
            Cancel (F4)
          </button>
        </div>

        <fieldset className="trading-account-items" disabled={fieldsLocked}>
          <div className="trading-account-item-columns">
            {renderItemList("raw", filteredRaw, rawSelected, rawSearch, setRawSearch)}
            {renderItemList(
              "finished",
              filteredFinished,
              finishedSelected,
              finishedSearch,
              setFinishedSearch,
            )}
          </div>
        </fieldset>

        <footer className="trading-account-status">
          {error ? <span className="trading-account-error">{error}</span> : null}
          {!error && status ? <span className="trading-account-ok">{status}</span> : null}
        </footer>
      </form>

      {findOpen && mode === "modify" && (
        <div className="trading-account-find-overlay" role="presentation">
          <div className="trading-account-find-panel" role="dialog" aria-modal="true">
            <header>
              <strong>Find Trading Account (F5)</strong>
              <button type="button" aria-label="Close" onClick={() => setFindOpen(false)}>
                ×
              </button>
            </header>
            <form
              className="trading-account-find-search"
              onSubmit={(event) => {
                event.preventDefault();
                void runFind(findQuery);
              }}
            >
              <input
                placeholder="ID / name / P&amp;L account"
                value={findQuery}
                onChange={(event) => {
                  setFindQuery(event.target.value);
                  void refreshFindList(event.target.value);
                }}
              />
              <button type="submit">Search</button>
            </form>
            <div className="trading-account-find-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>P / L A/c</th>
                  </tr>
                </thead>
                <tbody>
                  {findRows.map((row) => (
                    <tr
                      key={String(row.trading_account_id)}
                      tabIndex={0}
                      onDoubleClick={() => applyRecord(row)}
                    >
                      <td>{String(row.trading_code ?? row.trading_account_id ?? "")}</td>
                      <td>{String(row.name ?? "")}</td>
                      <td>{String(row.profit_loss_account ?? "")}</td>
                    </tr>
                  ))}
                  {!findRows.length && (
                    <tr>
                      <td colSpan={3}>No trading accounts found.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      <DeleteConfirmModal
        open={deleteOpen}
        recordLabel={accountName || "this trading account"}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => void confirmDelete()}
      />
    </>
  );
}
