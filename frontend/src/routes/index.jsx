import { createBrowserRouter } from "react-router-dom"
import HomeLayout from "@/layout/HomeLayout"
import TripFlowLayout from "@/templates/TripFlowLayout"
import Home from "@/pages/Home"
import Auth from "@/pages/Auth"
import NewTrip from "@/pages/NewTrip"
import InvitesSent from "@/pages/InvitesSent"
import TripPreferences from "@/pages/TripPreferences"
import TripLobby from "@/pages/TripLobby"
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
      { path: "/trips/lobby",         element: <ProtectedRoute><TripLobby /></ProtectedRoute> },
      { path: "/trips/:tripId/lobby", element: <ProtectedRoute><TripLobby /></ProtectedRoute> },
    ],
  },
])

export default router
