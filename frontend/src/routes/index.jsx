import { createBrowserRouter } from "react-router-dom"
import RootLayout from "@/layout/RootLayout"
import HomeLayout from "@/layout/HomeLayout"
import Home from "@/pages/Home"
import NewTrip from "@/pages/NewTrip"
import Dashboard from "@/pages/Dashboard"

sessionStorage.clear()

const router = createBrowserRouter([
  {
    element: <HomeLayout />,
    children: [
      { path: "/",          element: <Home /> },
      { path: "/trips/new", element: <NewTrip /> },
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
