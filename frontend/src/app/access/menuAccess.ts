import type { MenuEntry, TopMenu } from "../routing/menuRegistry";
import { topMenus } from "../routing/menuRegistry";
import { resolveWindowTitle } from "../routing/windowRouting";

export type UserSession = {
  user_id: string;
  username: string;
  display_name: string;
  role: string;
  can_view_kachi: boolean;
  use_custom_menu: boolean;
  permissions: Record<string, string>;
  access_valid_until?: string;
};

function permissionKeyForWindow(windowTitle: string): string {
  return resolveWindowTitle(windowTitle).screen || windowTitle;
}

function leafAllowed(windowTitle: string, session: UserSession | null): boolean {
  if (!session) return true;
  if (session.role === "admin" || !session.use_custom_menu) return true;
  const key = permissionKeyForWindow(windowTitle);
  return Boolean(session.permissions[key]);
}

function filterEntry(entry: MenuEntry, session: UserSession | null): MenuEntry | null {
  if (entry.kind === "leaf") {
    if (entry.disabled) return entry;
    return leafAllowed(entry.window, session) ? entry : null;
  }
  const children = entry.children
    .map((child) => filterEntry(child, session))
    .filter((child): child is MenuEntry => child !== null);
  if (!children.length) return null;
  return { ...entry, children };
}

export function filterTopMenus(session: UserSession | null): TopMenu[] {
  return topMenus
    .map((menu) => {
      const items = menu.items
        .map((entry) => filterEntry(entry, session))
        .filter((entry): entry is MenuEntry => entry !== null);
      if (!items.length) return null;
      return { ...menu, items };
    })
    .filter((menu): menu is TopMenu => menu !== null);
}

export function windowAccessLevel(
  windowTitle: string,
  session: UserSession | null,
): "write" | "read" | "none" {
  if (!session) return "write";
  if (session.role === "admin" || !session.use_custom_menu) {
    if (session.role === "clerk" || session.role === "readonly") return "read";
    return "write";
  }
  const key = permissionKeyForWindow(windowTitle);
  const level = session.permissions[key];
  if (level === "write") return "write";
  if (level === "read") return "read";
  return "none";
}

export function canOpenWindow(windowTitle: string, session: UserSession | null): boolean {
  if (windowTitle === "__exit__" || windowTitle === "__calculator__") return true;
  if (!session) return true;
  if (session.role === "admin" || !session.use_custom_menu) return true;
  return windowAccessLevel(windowTitle, session) !== "none";
}
