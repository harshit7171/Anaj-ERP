import { FormEvent, useCallback, useEffect, useState } from "react";

import type { Result } from "../api/types";

type MandiRow = Record<string, string>;

type IntegrationApi = {
  fetch_mandi_bhav?(
    state: string,
    commodity: string,
    limit: number,
  ): Promise<Result & { rows?: MandiRow[]; source?: string; notice?: string }>;
  auction_board_snapshot?(): Promise<Result & { lots?: Record<string, unknown>[] }>;
  upsert_auction_lot?(payload: Record<string, unknown>): Promise<Result>;
  place_auction_bid?(payload: Record<string, unknown>): Promise<Result>;
  close_auction_lot?(lotId: string): Promise<Result>;
};

export function MandiBhavOnline({ api }: { api: IntegrationApi }) {
  const [state, setState] = useState("Haryana");
  const [commodity, setCommodity] = useState("");
  const [rows, setRows] = useState<MandiRow[]>([]);
  const [source, setSource] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  async function load(event?: FormEvent) {
    event?.preventDefault();
    setError("");
    const response = await api.fetch_mandi_bhav?.(state, commodity, 50);
    if (!response?.ok) {
      setError(response?.error ?? "Fetch failed");
      return;
    }
    setRows(response.rows ?? []);
    setSource(String(response.source ?? ""));
    setNotice(String(response.notice ?? ""));
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <section className="entry-form p-2 text-xs mandi-bhav-screen">
      <h2>Mandi Bhav (Agmarknet)</h2>
      <p className="status-message">
        Live modal prices when `agmarknet_api_key` is set under Company Parameters; otherwise sample rows for demo.
      </p>
      <form className="flex flex-wrap gap-2 items-end" onSubmit={(event) => void load(event)}>
        <label>
          State
          <input value={state} onChange={(e) => setState(e.target.value)} />
        </label>
        <label>
          Commodity
          <input value={commodity} onChange={(e) => setCommodity(e.target.value)} placeholder="Wheat" />
        </label>
        <button type="submit">Refresh</button>
      </form>
      {source && <p className="text-slate-600">Source: {source}</p>}
      {notice && <p className="status-message">{notice}</p>}
      {error && <p className="text-red-700">{error}</p>}
      <table className="sortable-table mt-2">
        <thead>
          <tr>
            <th>Market</th>
            <th>Commodity</th>
            <th>Modal ₹/qtl</th>
            <th>Min</th>
            <th>Max</th>
            <th>Date</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${row.market}-${index}`}>
              <td>{row.market}</td>
              <td>{row.commodity}</td>
              <td>{row.modal_price}</td>
              <td>{row.min_price}</td>
              <td>{row.max_price}</td>
              <td>{row.price_date}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export function LiveBoliBoard({ api, tvMode = false }: { api: IntegrationApi; tvMode?: boolean }) {
  const [lots, setLots] = useState<Record<string, unknown>[]>([]);
  const [lotNo, setLotNo] = useState("");
  const [commodity, setCommodity] = useState("");
  const [bidder, setBidder] = useState("");
  const [bid, setBid] = useState("");
  const [message, setMessage] = useState("");

  const refresh = useCallback(async () => {
    const response = await api.auction_board_snapshot?.();
    if (response?.ok && response.lots) setLots(response.lots);
  }, [api]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 8000);
    return () => {
      window.clearInterval(timer);
    };
  }, [refresh]);

  async function addLot(event: FormEvent) {
    event.preventDefault();
    const response = await api.upsert_auction_lot?.({
      lot_no: lotNo,
      commodity,
      quantity_qtl: 100,
      current_bid_rupees: Number(bid || 0),
      bidder: bidder || "—",
      status: "open",
    });
    setMessage(response?.ok ? "Lot saved." : response?.error ?? "Failed");
    if (response?.ok) void refresh();
  }

  async function submitBid(lotId: string) {
    const response = await api.place_auction_bid?.({
      lot_id: lotId,
      bid_rupees: Number(bid),
      bidder,
    });
    setMessage(response?.ok ? "Bid placed." : response?.error ?? "Bid rejected");
    if (response?.ok) void refresh();
  }

  return (
    <section className={`boli-board ${tvMode ? "boli-board-tv" : ""}`}>
      <header className="boli-board-header">
        <h2>Live Boli — Mandi Auction Board</h2>
        <p>Open on a second monitor/TV (F11 fullscreen). Updates via LAN WebSocket when on office server.</p>
      </header>
      {!tvMode && (
        <form className="entry-form p-2 text-xs flex flex-wrap gap-2" onSubmit={(event) => void addLot(event)}>
          <label>
            Lot no
            <input value={lotNo} onChange={(e) => setLotNo(e.target.value)} required />
          </label>
          <label>
            Commodity
            <input value={commodity} onChange={(e) => setCommodity(e.target.value)} />
          </label>
          <label>
            Opening bid ₹
            <input value={bid} onChange={(e) => setBid(e.target.value)} />
          </label>
          <label>
            Bidder
            <input value={bidder} onChange={(e) => setBidder(e.target.value)} />
          </label>
          <button type="submit">Add / update lot</button>
        </form>
      )}
      {message && <p className="status-message px-2">{message}</p>}
      <div className="boli-board-grid">
        {lots.map((lot) => (
          <article className="boli-lot-card" key={String(lot.lot_id)}>
            <div className="boli-lot-no">{String(lot.lot_no)}</div>
            <div className="boli-commodity">{String(lot.commodity)}</div>
            <div className="boli-price">₹ {String(lot.current_bid_rupees)} / qtl</div>
            <div className="boli-bidder">{String(lot.bidder || "—")}</div>
            <div className="boli-status">{String(lot.status)}</div>
            {!tvMode && (
              <button type="button" onClick={() => void submitBid(String(lot.lot_id))}>
                Place bid (uses fields above)
              </button>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}

export function isIntegrationScreen(title: string): boolean {
  return title === "Mandi Bhav Online" || title === "Live Boli Board" || title === "Live Boli Board (TV)";
}

export function IntegrationScreenRouter({ title, api }: { title: string; api: IntegrationApi }) {
  if (title === "Mandi Bhav Online") return <MandiBhavOnline api={api} />;
  if (title === "Live Boli Board" || title === "Live Boli Board (TV)") {
    return <LiveBoliBoard api={api} tvMode={title.includes("TV")} />;
  }
  return null;
}
