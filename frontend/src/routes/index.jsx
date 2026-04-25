import { createBrowserRouter } from "react-router-dom"
import RootLayout from "@/layout/RootLayout"
import HomeLayout from "@/layout/HomeLayout"
import TripFlowLayout from "@/templates/TripFlowLayout"
import Home from "@/pages/Home"
import NewTrip from "@/pages/NewTrip"
import TripPreferences from "@/pages/TripPreferences"
import Dashboard from "@/pages/Dashboard"

sessionStorage.clear()

const router = createBrowserRouter([
  {
    element: <HomeLayout />,
    children: [
      { path: "/", element: <Home /> },
    ],
  },
  {
    element: <TripFlowLayout />,
    children: [
      { path: "/trips/new",         element: <NewTrip /> },
      { path: "/trips/preferences", element: <TripPreferences /> },
    ],
  },
  {
    element: <RootLayout />,
    children: [
      { path: "/dashboard", element: <Dashboard /> },
    ],
  },
])

export default router
