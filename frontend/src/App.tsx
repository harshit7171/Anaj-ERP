import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import type { Company, FinancialYear, LicenseStatus } from "./api/types";
import Button from "./components/Button";
import Modal from "./components/Modal";
import SettingsModal from "./components/SettingsModal";
import EntryWindow from "./EntryWindow";
import TransactionWindowModal from "./components/TransactionWindowModal";
import BentoDashboard from "./screens/BentoDashboard";
import CalculatorFabIcon from "./components/CalculatorFabIcon";
import CalculatorPopup, { CALCULATOR_WINDOW } from "./components/CalculatorPopup";
import FlyoutMenuBar from "./components/FlyoutMenuBar";
import QuickDailyDock from "./components/QuickDailyDock";
import {
  canOpenWindow,
  filterTopMenus,
  type UserSession,
  windowAccessLevel,
} from "./app/access/menuAccess";
import { resolveWindowTitle } from "./app/routing/windowRouting";
import UserLoginModal from "./screens/UserLoginModal";

type ApiResult = {
  ok: boolean;
  error?: string;
  companies?: Company[];
  company?: Company;
  financial_years?: FinancialYear[];
};

type DesktopApi = import("./api/types").DesktopApi;

const shortcuts = [
  { key: "F2", label: "Cash Book" },
  { key: "F3", label: "Journal" },
  { key: "F4", label: "Form - J" },
  { key: "F5", label: "Form - I (Dr.)" },
  { key: "F6", label: "New Commodity" },
  { key: "F7", label: "New Ledger" },
  { key: "F11", label: "Form - I (Cr.)" },
  { key: "F12", label: "Transfer Challan" },
  { key: "F9", label: "Account Balance" },
  { key: "", label: "Commodity Balance" },
  { key: "", label: "Trial Balance" },
  { key: "", label: "Interest" },
];

function currentFinancialYear(): number {
  const now = new Date();
  return now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1;
}

function LicenseNotice({
  phase,
  warning,
  reason,
  onClose,
}: {
  phase: LicenseStatus["phase"];
  warning: string;
  reason: string;
  onClose(): void;
}) {
  if (phase === "warning" || phase === "demo") {
    return (
      <aside className="license-warning-toast" role="status">
        <strong>{phase === "demo" ? "Demo Mode" : "Renewal Reminder"}</strong>
        <span>{warning}</span>
        <button type="button" onClick={onClose}>Close</button>
      </aside>
    );
  }
  if (phase !== "expired" && phase !== "clock_tamper" && phase !== "demo_expired") return null;
  return (
    <div className="blocking-modal license-blocker" role="alertdialog" aria-modal="true">
      <div className="saved-dialog">
        <header><span>Anaj Accounting ERP</span></header>
        <p>
          {phase === "demo_expired"
            ? reason || "15-day demo expired. Enter a license key to continue."
            : phase === "expired"
              ? "Subscription Expired. Please contact support to renew your license key."
              : reason || "System clock rollback detected. Correct the Windows date and contact support."}
        </p>
        {(phase === "expired" || phase === "demo_expired") && (
          <button type="button" onClick={onClose}>Continue Read Only</button>
        )}
      </div>
    </div>
  );
}

function App() {
  const [bridgeReady, setBridgeReady] = useState(() => Boolean(window.pywebview?.api));
  const [companies, setCompanies] = useState<Company[]>([]);
  const [years, setYears] = useState<FinancialYear[]>([]);
  const [companyId, setCompanyId] = useState("");
  const [yearId, setYearId] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [kachiCompany, setKachiCompany] = useState(false);
  const [startYear, setStartYear] = useState(currentFinancialYear());
  const [activeCompany, setActiveCompany] = useState<Company | null>(null);
  const [activeYear, setActiveYear] = useState<FinancialYear | null>(null);
  const [activeWindow, setActiveWindow] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [licenseValid, setLicenseValid] = useState<boolean | null>(null);
  const [licenseWritable, setLicenseWritable] = useState(false);
  const [licensePhase, setLicensePhase] = useState<LicenseStatus["phase"]>();
  const [licenseReason, setLicenseReason] = useState("");
  const [licenseWarning, setLicenseWarning] = useState("");
  const [showLicenseNotice, setShowLicenseNotice] = useState(false);
  const [licenseKey, setLicenseKey] = useState("");
  const [installationId, setInstallationId] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [tdsReminderOpen, setTdsReminderOpen] = useState(false);
  const [navigationPinned, setNavigationPinned] = useState(false);
  const [navigationHovered, setNavigationHovered] = useState(false);
  const [calculatorOpen, setCalculatorOpen] = useState(false);
  const [loginRequired, setLoginRequired] = useState(false);
  const [userSession, setUserSession] = useState<UserSession | null>(null);

  const api = window.pywebview?.api;
  const filteredMenus = useMemo(() => filterTopMenus(userSession), [userSession]);
  const mustLogin = loginRequired && !userSession;

  function openWindow(windowTitle: string) {
    if (
      windowTitle === CALCULATOR_WINDOW ||
      resolveWindowTitle(windowTitle).screen === CALCULATOR_WINDOW
    ) {
      setCalculatorOpen(true);
      return;
    }
    if (!canOpenWindow(windowTitle, userSession)) {
      setError("This screen is not enabled for your user.");
      return;
    }
    setActiveWindow(windowTitle);
  }

  const applyLicenseStatus = useCallback((status: LicenseStatus | undefined) => {
    setLicenseValid(Boolean(status?.valid));
    setLicenseWritable(Boolean(status?.writable));
    setLicensePhase(status?.phase);
    setLicenseReason(status?.reason ?? "");
    setLicenseWarning(status?.warning_message ?? "");
    setShowLicenseNotice(
      status?.phase === "warning"
        || status?.phase === "demo"
        || status?.phase === "expired"
        || status?.phase === "demo_expired"
        || status?.phase === "clock_tamper",
    );
  }, []);

  const loadCompanies = useCallback(async () => {
    if (!window.pywebview?.api) return;
    const result = await window.pywebview.api.list_companies();
    if (!result.ok) {
      setError(result.error ?? "Unable to load companies");
      return;
    }
    let loaded = result.companies ?? [];
    if (localStorage.getItem("anajHideKachi") === "1") {
      loaded = loaded.filter((company) => company.company_profile !== "kachi");
    }
    if (userSession && !userSession.can_view_kachi) {
      loaded = loaded.filter((company) => company.company_profile !== "kachi");
    }
    setCompanies(loaded);
    if (loaded.length && !companyId) setCompanyId(loaded[0].company_id);
  }, [companyId, userSession]);

  const refreshAuth = useCallback(async () => {
    if (!window.pywebview?.api) return;
    const status = await window.pywebview.api.user_login_status();
    if (!status.ok) return;
    setLoginRequired(Boolean(status.login_required));
    const session = status.session as UserSession | null | undefined;
    setUserSession(session ?? null);
  }, []);

  const bootstrapApi = useCallback(async () => {
    if (!window.pywebview?.api) return;
    setBridgeReady(true);
    await refreshAuth();
    await loadCompanies();
    const result = await window.pywebview.api.health();
    setInstallationId(result.installation_id ?? "");
    applyLicenseStatus(result.license);
  }, [applyLicenseStatus, loadCompanies, refreshAuth]);

  useEffect(() => {
    const ready = () => {
      void bootstrapApi();
    };
    window.addEventListener("pywebviewready", ready);
    if (window.pywebview?.api) void bootstrapApi();
    return () => window.removeEventListener("pywebviewready", ready);
  }, [bootstrapApi]);

  useEffect(() => {
    if (!api) return;
    const refreshLicense = () => {
      void api.license_status().then((status) => {
        if (status.ok) applyLicenseStatus(status);
      });
    };
    const timer = window.setInterval(refreshLicense, 60_000);
    window.addEventListener("focus", refreshLicense);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", refreshLicense);
    };
  }, [api, applyLicenseStatus]);

  useEffect(() => {
    if (!api || !activeCompany) return;
    const monthKey = new Date().toISOString().slice(0, 7);
    const seenKey = `tdsReminderShownFor:${activeCompany.company_id}:${monthKey}`;
    void api.compliance_status().then((response) => {
      if (!response.ok || !response.compliance?.show_tds_reminder) return;
      if (sessionStorage.getItem(seenKey)) return;
      setTdsReminderOpen(true);
      sessionStorage.setItem(seenKey, "1");
    });
  }, [api, activeCompany]);

  useEffect(() => {
    if (!api || !companyId) {
      setYears([]);
      setYearId("");
      return;
    }
    void api.list_financial_years(companyId).then((result) => {
      if (!result.ok) {
        setError(result.error ?? "Unable to load financial years");
        return;
      }
      const loaded = result.financial_years ?? [];
      setYears(loaded);
      setYearId(loaded[0]?.financial_year_id ?? "");
    });
  }, [api, companyId]);

  const selectedCompany = useMemo(
    () => companies.find((company) => company.company_id === companyId),
    [companies, companyId],
  );

  const selectedYear = useMemo(
    () => years.find((year) => year.financial_year_id === yearId),
    [years, yearId],
  );

  async function createCompany(event: FormEvent) {
    event.preventDefault();
    if (!api || !companyName.trim()) return;
    setBusy(true);
    setError("");
    const result = await api.create_company(
      companyName,
      startYear,
      kachiCompany ? "kachi" : "standard",
    );
    setBusy(false);
    if (!result.ok) {
      setError(result.error ?? "Company could not be created");
      return;
    }
    setCompanyName("");
    await loadCompanies();
    if (result.company) setCompanyId(result.company.company_id);
  }

  async function switchUser() {
    if (!api) return;
    await api.user_logout();
    setUserSession(null);
    setActiveCompany(null);
    setActiveYear(null);
    setActiveWindow("");
    await refreshAuth();
  }

  async function openCompany() {
    if (!api || !selectedCompany || !selectedYear || mustLogin) return;
    setBusy(true);
    setError("");
    const result = await api.select_context(
      selectedCompany.company_id,
      selectedYear.financial_year_id,
    );
    setBusy(false);
    if (!result.ok) {
      setError(result.error ?? "Company could not be opened");
      return;
    }
    setActiveCompany(selectedCompany);
    setActiveYear(selectedYear);
  }

  async function activateLicense(event: FormEvent) {
    event.preventDefault();
    if (!api || !licenseKey.trim()) return;
    setBusy(true);
    const result = await api.install_license(licenseKey.trim());
    setBusy(false);
    if (!result.ok) {
      setError(result.error ?? "License could not be installed");
      return;
    }
    applyLicenseStatus(result.license);
    setLicenseKey("");
    setError("");
  }

  useEffect(() => {
    if (!activeCompany) return;
    const keyHandler = (event: KeyboardEvent) => {
      if (event.ctrlKey && event.key.toLowerCase() === "s") {
        event.preventDefault();
        setActiveWindow("Sale Invoice");
        return;
      }
      if (event.ctrlKey && event.key.toLowerCase() === "p") {
        event.preventDefault();
        setActiveWindow("Purchase Invoice");
        return;
      }
      if (event.ctrlKey && event.key.toLowerCase() === "a") {
        const target = event.target as HTMLElement | null;
        const tag = target?.tagName ?? "";
        if (tag !== "INPUT" && tag !== "TEXTAREA" && tag !== "SELECT") {
          event.preventDefault();
          setActiveWindow("Account Master Add");
          return;
        }
      }
      const shortcut = shortcuts.find((item) => item.key === event.key);
      if (shortcut) {
        event.preventDefault();
        setActiveWindow(shortcut.label);
      }
    };
    window.addEventListener("keydown", keyHandler);
    return () => window.removeEventListener("keydown", keyHandler);
  }, [activeCompany]);

  const canOpenCompany = ["active", "warning", "expired", "demo", "demo_expired"].includes(
    licensePhase ?? "",
  );

  if (!activeCompany || !activeYear) {
    return (
      <main className="startup-shell">
        {mustLogin && api && (
          <UserLoginModal
            api={api}
            onLoggedIn={(session) => {
              setUserSession(session);
              void loadCompanies();
            }}
          />
        )}
        <section className="company-panel" aria-labelledby="company-heading">
          <h1 id="company-heading">Aapka Business Aapka Software</h1>
          <p className="status-message">Standalone mode — all companies and data stay on this PC.</p>
          <div className="company-table" role="listbox" aria-label="Company list">
            <div className="company-table-header">
              <span>COMPANY LIST</span>
              <span>CODE</span>
            </div>
            {companies.map((company, index) => (
              <button
                aria-selected={company.company_id === companyId}
                className={company.company_id === companyId ? "selected" : ""}
                key={company.company_id}
                onClick={() => setCompanyId(company.company_id)}
                role="option"
                type="button"
              >
                <span>{company.name}</span>
                <strong>Comp{index + 1}</strong>
              </button>
            ))}
            {!companies.length && <p>No company created</p>}
          </div>
          <div className="selector-grid">
            <label htmlFor="financial-year">Financial Year</label>
            <select
              id="financial-year"
              value={yearId}
              onChange={(event) => setYearId(event.target.value)}
            >
              {years.map((year) => (
                <option key={year.financial_year_id} value={year.financial_year_id}>
                  {year.label}{year.is_locked ? " (Locked)" : ""}
                </option>
              ))}
            </select>
          </div>
          <button
            className="primary-button"
            disabled={
              !bridgeReady || !canOpenCompany || !selectedCompany || !selectedYear || busy || mustLogin
            }
            onClick={() => void openCompany()}
          >
            Open Company
          </button>
          {userSession && (
            <p className="status-message">
              Signed in as {userSession.display_name || userSession.username}
              {userSession.role !== "admin" ? " (restricted menus)" : " (owner)"}
            </p>
          )}
          {loginRequired && userSession && (
            <button type="button" onClick={() => void switchUser()}>
              Switch user
            </button>
          )}

          {licenseValid === false && (
            <form className="license-panel" onSubmit={(event) => void activateLicense(event)}>
              <h2>Annual Access Key Required</h2>
              <p>{licenseReason || "Contact support to renew access through April 30."}</p>
              <small>Installation ID: {installationId}</small>
              <textarea
                aria-label="Annual license key"
                placeholder="Paste the key supplied during AnyDesk support"
                value={licenseKey}
                onChange={(event) => setLicenseKey(event.target.value)}
              />
              <button disabled={busy || !licenseKey.trim()} type="submit">
                Activate
              </button>
            </form>
          )}

          <form className="create-company" onSubmit={(event) => void createCompany(event)}>
            <h2>Create Company</h2>
            <input
              aria-label="New company name"
              placeholder="Company name"
              value={companyName}
              onChange={(event) => setCompanyName(event.target.value)}
            />
            <select
              aria-label="Financial year start"
              value={startYear}
              onChange={(event) => setStartYear(Number(event.target.value))}
            >
              {Array.from({ length: 9 }, (_, index) => currentFinancialYear() - 4 + index).map(
                (year) => <option key={year} value={year}>{year}-{year + 1}</option>,
              )}
            </select>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={kachiCompany}
                onChange={(event) => setKachiCompany(event.target.checked)}
              />
              Kachi / Dasti company (hidden from users without Kachi access)
            </label>
            <button disabled={!bridgeReady || !licenseWritable || busy || !companyName.trim()} type="submit">
              Create
            </button>
          </form>
          {!bridgeReady && (
            <p className="status-message">Connecting to the local desktop service…</p>
          )}
          {error && <p className="error-message">{error}</p>}
          {showLicenseNotice && (
            <LicenseNotice
              phase={licensePhase}
              warning={licenseWarning}
              reason={licenseReason}
              onClose={() => setShowLicenseNotice(false)}
            />
          )}
        </section>

        <section className="ganesha-panel" aria-label="Welcome">
          <div className="ganesha-title">श्री गणेशाय नमः</div>
          <div className="ganesha-mark">
            <img src="./ganesha-welcome.png" alt="Lord Ganesha" />
          </div>
          <div className="product-copy">
            <strong>Accounting Software</strong>
            <span>Anaj ERP</span>
            <small>For Commission Agents &amp; Grain Traders</small>
          </div>
        </section>
      </main>
    );
  }

  const embeddedActionWindows = [
    "Cash Book",
    "Journal",
    "Accounting Voucher",
    "Voucher Entry",
    "TDS Challan Entry",
    "Bank Reconciliation",
    "Find Account",
    "Depreciation Chart",
    "Stock Adjustment",
    "Company Letter Head Print",
    "Debit Note",
    "Credit Note",
    "Form - J",
    "Form - I (Dr.)",
    "Form - I (Cr.)",
    "Sale Invoice",
    "Purchase Invoice",
    "Transfer Challan",
    "Delivery Challan",
    "Gate Pass",
    "Sale Memo",
    "Purchase Memo",
    "Inward",
    "Outward",
    "Consignment (Dr.)",
    "Consignment (Cr.)",
    "Milling Inward",
    "Milling Outward",
    "Packing Material Transfer",
  ];

  return (
    <main
      className={`desktop-shell ${
        navigationPinned || navigationHovered ? "navigation-expanded" : ""
      }`}
    >
      {showLicenseNotice && (
        <LicenseNotice
          phase={licensePhase}
          warning={licenseWarning}
          reason={licenseReason}
          onClose={() => setShowLicenseNotice(false)}
        />
      )}
      <header className="menu-bar">
        <div className="menu-brand">
          <button
            aria-controls="primary-navigation"
            aria-expanded={navigationPinned}
            aria-label={navigationPinned ? "Collapse navigation" : "Open navigation"}
            className="navigation-toggle"
            onClick={() => setNavigationPinned((open) => !open)}
            type="button"
          >
            <span aria-hidden="true">☰</span>
          </button>
          <strong>
            Anaj ERP <span>| {activeCompany.name} | {activeYear.label}</span>
            {userSession && (
              <span className="menu-user-tag">
                {" "}
                | User: {userSession.display_name || userSession.username}
              </span>
            )}
          </strong>
        </div>
        <nav aria-label="Application menu">
          <FlyoutMenuBar
            menus={filteredMenus}
            onOpenWindow={openWindow}
            onExit={() => {
              if (window.pywebview?.api) {
                window.close();
              }
            }}
            extra={(
              <>
                {userSession?.role === "admin" && (
                  <button type="button" onClick={() => setActiveWindow("Configuration")}>
                    Administrator
                  </button>
                )}
                {loginRequired && (
                  <button type="button" onClick={() => void switchUser()}>
                    Switch user
                  </button>
                )}
                <button aria-label="Settings" title="Settings" type="button" onClick={() => setSettingsOpen(true)}>
                  ⚙
                </button>
              </>
            )}
          />
        </nav>
      </header>
      {settingsOpen && api && <SettingsModal api={api as never} onClose={() => setSettingsOpen(false)} />}
      {tdsReminderOpen && (
        <Modal
          tone="warning"
          title="Monthly TDS Compliance Checklist"
          onClose={() => setTdsReminderOpen(false)}
          footer={
            <>
              <Button type="button" onClick={() => setTdsReminderOpen(false)}>
                Dismiss
              </Button>
              <Button
                type="button"
                variant="primary"
                onClick={() => {
                  setActiveWindow("TDS Register");
                  setTdsReminderOpen(false);
                }}
              >
                Review TDS Liability
              </Button>
            </>
          }
        >
          Please review pending Tax Deducted at Source (TDS) calculations on commission payments
          and deposit submissions with the government before the statutory deadline.
        </Modal>
      )}
      <button
        aria-label="Open calculator"
        className="calc-fab"
        type="button"
        onClick={() => setCalculatorOpen(true)}
      >
        <CalculatorFabIcon />
      </button>
      <CalculatorPopup open={calculatorOpen} onClose={() => setCalculatorOpen(false)} />
      <QuickDailyDock onOpen={openWindow} />
      <section className="workspace">
        {activeWindow && (
          <TransactionWindowModal
            onClose={() => setActiveWindow("")}
            title={activeWindow}
          >
            <EntryWindow
              title={activeWindow}
              readOnly={windowAccessLevel(activeWindow, userSession) === "read"}
              onExit={() => setActiveWindow("")}
            />
          </TransactionWindowModal>
        )}
        {api ? (
          <BentoDashboard api={api as never} />
        ) : (
          <div className="desktop-welcome">
            <span>Company: {activeCompany.name}</span>
            <strong>Financial Year: {activeYear.label}</strong>
          </div>
        )}
      </section>
      <div
        aria-hidden="true"
        className="navigation-hover-trigger"
        onMouseEnter={() => setNavigationHovered(true)}
      />
      <aside
        className={`shortcut-rail ${navigationPinned || navigationHovered ? "is-expanded" : ""}`}
        id="primary-navigation"
        onMouseEnter={() => setNavigationHovered(true)}
        onMouseLeave={() => setNavigationHovered(false)}
      >
        <div className="clock-card">{new Date().toLocaleDateString("en-IN")}</div>
        <h2>Entry</h2>
        {shortcuts.map((shortcut) => (
          <button
            key={`${shortcut.key}-${shortcut.label}`}
            onClick={() => setActiveWindow(shortcut.label)}
          >
            <strong>{shortcut.key}</strong>
            <span>{shortcut.label}</span>
          </button>
        ))}
        <button onClick={() => setActiveWindow("New Party")}>
          <strong>Ctrl+N</strong><span>New Party</span>
        </button>
        <button onClick={() => setActiveWindow("Sale Invoice")}>
          <strong>Ctrl+S</strong><span>Sale Invoice</span>
        </button>
        <button onClick={() => setActiveWindow("Purchase Invoice")}>
          <strong>Ctrl+P</strong><span>Purchase Invoice</span>
        </button>
        <button onClick={() => setActiveWindow("Farmer Credit Dashboard")}>
          <strong>FC</strong><span>Farmer Credit</span>
        </button>
        <button
          className="configuration-button"
          onClick={() => setActiveWindow("Configuration")}
        >
          Configuration
        </button>
        <button onClick={() => {
          setActiveCompany(null);
          setActiveYear(null);
          setActiveWindow("");
        }}>
          Select Other Company
        </button>
      </aside>
    </main>
  );
}

export default App;
