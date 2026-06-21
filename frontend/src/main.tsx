import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { App } from "./App";
import { AuthProvider, RequireArea } from "./components/auth";
import { BrandProvider } from "./components/brand-provider";
import { ThemeProvider } from "./components/theme-provider";
import { Admin } from "./pages/Admin";
import { AdminGroups } from "./pages/AdminGroups";
import { AdminSessionRaw } from "./pages/AdminSessionRaw";
import { AdminUser } from "./pages/AdminUser";
import { Analytics } from "./pages/Analytics";
import { Assets } from "./pages/Assets";
import { Chat } from "./pages/Chat";
import { Dashboards } from "./pages/Dashboards";
import { DashboardView } from "./pages/DashboardView";
import { Dbt } from "./pages/Dbt";
import { Home } from "./pages/Home";
import { Semantic } from "./pages/Semantic";
import { Sessions } from "./pages/Sessions";
import "./index.css";

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("Root element #root not found");
createRoot(rootElement).render(
  <StrictMode>
    {/* ThemeProvider OUTERMOST — BrandProvider reads the active theme to pick light/dark tokens. */}
    <ThemeProvider>
      <BrandProvider>
        <BrowserRouter>
          <AuthProvider>
            <Routes>
              <Route element={<App />}>
                <Route path="/" element={<Home />} />
                <Route path="/chat" element={<Chat />} />
                <Route path="/chat/:sessionId" element={<Chat />} />
                <Route path="/sessions" element={<Sessions />} />
                <Route path="/assets" element={<Assets />} />
                {/* RBAC-gated areas (the backend enforces these too). */}
                <Route
                  path="/analytics"
                  element={
                    <RequireArea area="analytics">
                      <Analytics />
                    </RequireArea>
                  }
                />
                <Route
                  path="/semantic"
                  element={
                    <RequireArea area="semantic">
                      <Semantic />
                    </RequireArea>
                  }
                />
                <Route
                  path="/dbt"
                  element={
                    <RequireArea area="dbt">
                      <Dbt />
                    </RequireArea>
                  }
                />
                <Route
                  path="/dashboards"
                  element={
                    <RequireArea area="dashboards">
                      <Dashboards />
                    </RequireArea>
                  }
                />
                <Route
                  path="/dashboards/:dashboardId"
                  element={
                    <RequireArea area="dashboards">
                      <DashboardView />
                    </RequireArea>
                  }
                />
                <Route
                  path="/admin"
                  element={
                    <RequireArea area="admin">
                      <Admin />
                    </RequireArea>
                  }
                />
                <Route
                  path="/admin/groups"
                  element={
                    <RequireArea area="admin">
                      <AdminGroups />
                    </RequireArea>
                  }
                />
                <Route
                  path="/admin/users/:userId"
                  element={
                    <RequireArea area="admin">
                      <AdminUser />
                    </RequireArea>
                  }
                />
                <Route
                  path="/admin/users/:userId/sessions/:sessionId"
                  element={
                    <RequireArea area="admin">
                      <AdminSessionRaw />
                    </RequireArea>
                  }
                />
              </Route>
            </Routes>
          </AuthProvider>
        </BrowserRouter>
      </BrandProvider>
    </ThemeProvider>
  </StrictMode>,
);
