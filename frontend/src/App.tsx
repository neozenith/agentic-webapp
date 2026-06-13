import { Outlet } from "react-router-dom";

import { Header } from "@/components/Header";
import { NavDrawerProvider } from "@/components/nav-drawer";
import { MobileNavDrawer, Sidebar } from "@/components/Sidebar";

export function App() {
  return (
    <NavDrawerProvider>
      <div className="flex min-h-screen">
        <Sidebar />
        <MobileNavDrawer />
        {/* min-w-0 lets the content column shrink below its intrinsic width inside the flex row
            (the flexbox min-width:auto trap) so nothing forces horizontal overflow on a phone. */}
        <div className="flex min-w-0 flex-1 flex-col">
          <Header />
          <main className="min-w-0 flex-1 overflow-y-auto p-4 md:p-6">
            <div className="mx-auto max-w-4xl">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </NavDrawerProvider>
  );
}
