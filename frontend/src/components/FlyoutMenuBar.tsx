import { type ReactNode, useState } from "react";

import type { MenuEntry, TopMenu } from "../menuRegistry";
import { topMenus as defaultTopMenus } from "../menuRegistry";

function MenuRow({
  entry,
  onSelect,
  depth = 0,
}: {
  entry: MenuEntry;
  onSelect(window: string): void;
  depth?: number;
}) {
  if (entry.kind === "leaf") {
    return (
      <button
        className={`menu-flyout-leaf${entry.disabled ? " is-disabled" : ""}`}
        disabled={entry.disabled}
        role="menuitem"
        type="button"
        onClick={() => {
          if (!entry.disabled) onSelect(entry.window);
        }}
      >
        <span>{entry.label}</span>
      </button>
    );
  }
  return (
    <div className={`menu-flyout-item depth-${depth}${entry.disabled ? " is-disabled" : ""}`}>
      <button
        className="menu-flyout-parent"
        disabled={entry.disabled}
        type="button"
        aria-haspopup="true"
      >
        <span>{entry.label}</span>
        <span className="menu-flyout-arrow" aria-hidden="true">
          ›
        </span>
      </button>
      <div className="entry-submenu" role="menu">
        {entry.children.map((child) => (
          <MenuRow key={child.label} entry={child} onSelect={onSelect} depth={depth + 1} />
        ))}
      </div>
    </div>
  );
}

function TopMenuDropdown({
  menu,
  open,
  onToggle,
  onSelect,
}: {
  menu: TopMenu;
  open: boolean;
  onToggle(): void;
  onSelect(window: string): void;
}) {
  return (
    <div className="menu-dropdown">
      <button aria-expanded={open} type="button" onClick={onToggle}>
        {menu.label}
      </button>
      {open && (
        <div className="entry-menu menu-flyout-root" role="menu">
          {menu.items.map((entry) => (
            <MenuRow key={entry.label} entry={entry} onSelect={onSelect} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function FlyoutMenuBar({
  onOpenWindow,
  onExit,
  extra,
  menus,
}: {
  onOpenWindow(window: string): void;
  onExit?(): void;
  extra?: ReactNode;
  menus?: TopMenu[];
}) {
  const [openId, setOpenId] = useState<string | null>(null);
  const topMenus = menus ?? defaultTopMenus;

  function select(window: string) {
    setOpenId(null);
    if (window === "__exit__") {
      onExit?.();
      return;
    }
    onOpenWindow(window);
  }

  return (
    <>
      {topMenus.map((menu) => (
        <TopMenuDropdown
          key={menu.id}
          menu={menu}
          open={openId === menu.id}
          onToggle={() => setOpenId((current) => (current === menu.id ? null : menu.id))}
          onSelect={select}
        />
      ))}
      {extra}
    </>
  );
}
