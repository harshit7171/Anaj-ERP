import type { AccountMasterApi } from "./types";

export function accountMasterApi(): AccountMasterApi | undefined {
  return window.pywebview?.api as unknown as AccountMasterApi | undefined;
}
