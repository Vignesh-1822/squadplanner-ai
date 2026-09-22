import { createBrowserRouter, Navigate } from "react-router-dom"
import HomeLayout from "@/layout/HomeLayout"
import TripFlowLayout from "@/templates/TripFlowLayout"
import Home from "@/pages/Home"
import Auth from "@/pages/Auth"
import NewTrip from "@/pages/NewTrip"
import InvitesSent from "@/pages/InvitesSent"
import TripPreferences from "@/pages/TripPreferences"
import TripLobby from "@/pages/TripLobby"
import Planning from "@/pages/Planning"
import TripHubLayout from "@/templates/TripHubLayout"
import HubOverview from "@/pages/hub/Overview"
import HubItinerary from "@/pages/hub/Itinerary"
import MyTrips from "@/pages/MyTrips"
import ProtectedRoute from "@/atoms/ProtectedRoute"

const router = createBrowserRouter([
  {
    element: <HomeLayout />,
    children: [
      { path: "/", element: <Home /> },
      { path: "/mytrips", element: <ProtectedRoute><MyTrips /></ProtectedRoute> },
    ],
  },
  {
    path: "/auth",
    element: <Auth />,
  },
  {
    element: <TripFlowLayout />,
    children: [
      { path: "/trips/new",          element: <ProtectedRoute><NewTrip /></ProtectedRoute> },
      { path: "/trips/invites-sent", element: <ProtectedRoute><InvitesSent /></ProtectedRoute> },
      { path: "/trips/:tripId/preferences", element: <ProtectedRoute><TripPreferences /></ProtectedRoute> },
      { path: "/trips/:tripId/lobby", element: <ProtectedRoute><TripLobby /></ProtectedRoute> },
      { path: "/trips/:tripId/planning", element: <ProtectedRoute><Planning /></ProtectedRoute> },
    ],
  },
  {
    // The hub fetches the itinerary once and shares it with every tab, so switching tabs
    // re-renders rather than refetches.
    path: "/trips/:tripId/hub",
    element: <ProtectedRoute><TripHubLayout /></ProtectedRoute>,
    children: [
      { index: true, element: <Navigate to="overview" replace /> },
      { path: "overview", element: <HubOverview /> },
      { path: "itinerary", element: <HubItinerary /> },
    ],
  },
])

export default router
