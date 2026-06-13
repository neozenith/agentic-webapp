import { createContext, type ReactNode, useCallback, useContext, useMemo, useState } from "react";

interface NavDrawerValue {
  /** Is the mobile (< md) off-canvas nav drawer open? Always false on md+ (the rail is used). */
  open: boolean;
  /** Open/close the drawer (e.g. the Header hamburger toggles it). */
  toggle: () => void;
  /** Close the drawer (backdrop click, Escape, or a nav-item click). */
  close: () => void;
}

// Default is a no-op closed drawer so components (Header/Sidebar) still render in isolation
// — e.g. unit tests that mount only the Header — without a surrounding provider.
const noop = (): void => {};
const NavDrawerContext = createContext<NavDrawerValue>({
  open: false,
  toggle: noop,
  close: noop,
});

/** Shares the mobile nav-drawer open state between the Header hamburger and the drawer panel. */
export function NavDrawerProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const toggle = useCallback(() => setOpen((o) => !o), []);
  const close = useCallback(() => setOpen(false), []);
  const value = useMemo<NavDrawerValue>(() => ({ open, toggle, close }), [open, toggle, close]);
  return <NavDrawerContext.Provider value={value}>{children}</NavDrawerContext.Provider>;
}

export function useNavDrawer(): NavDrawerValue {
  return useContext(NavDrawerContext);
}
