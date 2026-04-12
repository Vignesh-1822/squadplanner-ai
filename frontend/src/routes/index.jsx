import { createBrowserRouter, redirect } from "react-router-dom"
import RootLayout from "@/layout/RootLayout"
import Home from "@/pages/Home"
import Dashboard from "@/pages/Dashboard"

sessionStorage.clear()

const router = createBrowserRouter([
  {
    element: <RootLayout />,
    loader: () => {
      if (!sessionStorage.getItem("hasVisited")) {
        sessionStorage.setItem("hasVisited", "true")
        return redirect("/")
      }
      return null
    },
    children: [
      {
        path: "/",
        element: <Home />,
      },
      {
        path: "/dashboard",
        element: <Dashboard />,
      },
    ],
  },
])

export default router
