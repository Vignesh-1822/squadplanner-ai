import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "leaflet/dist/leaflet.css";
import "./styles.css";
import { AppShell } from "./ui/AppShell.jsx";
import { TripInputPage } from "./pages/TripInputPage.jsx";
import { PlanningPage } from "./pages/PlanningPage.jsx";
import { ItineraryPage } from "./pages/ItineraryPage.jsx";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<TripInputPage />} />
          <Route path="/planning/:tripId" element={<PlanningPage />} />
          <Route path="/trip/:tripId" element={<ItineraryPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  </React.StrictMode>,
);
