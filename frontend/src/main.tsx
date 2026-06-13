import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { App } from "./App";
import { Admin } from "./pages/Admin";
import { AdminSessionRaw } from "./pages/AdminSessionRaw";
import { AdminUser } from "./pages/AdminUser";
import { Analytics } from "./pages/Analytics";
import { Assets } from "./pages/Assets";
import { Chat } from "./pages/Chat";
import { Home } from "./pages/Home";
import { Sessions } from "./pages/Sessions";
import "./index.css";

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("Root element #root not found");
createRoot(rootElement).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<App />}>
          <Route path="/" element={<Home />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/chat/:sessionId" element={<Chat />} />
          <Route path="/sessions" element={<Sessions />} />
          <Route path="/assets" element={<Assets />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="/admin/users/:userId" element={<AdminUser />} />
          <Route path="/admin/users/:userId/sessions/:sessionId" element={<AdminSessionRaw />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
