import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "./index.css";
import "./styles.css";
import "./styles/calculator-popup.css";
import "./styles/lifting-entry.css";
import "./styles/accounts-entry.css";
import "./styles/kachi-purchase.css";
import "./styles/mandi-purchase-entry.css";
import "./styles/gst-purchase-entry.css";
import "./styles/invoice-entry.css";
import "./styles/gst-debit-note-entry.css";
import "./styles/simple-note-entry.css";

document.body.classList.add("mandi-ui");

const root = document.getElementById("root");

if (!root) {
  throw new Error("Application root element was not found");
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
