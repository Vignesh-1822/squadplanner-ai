import { Outlet } from "react-router-dom"
import { Toaster } from "sonner"
import Logo from "@/atoms/Logo"

const TripFlowLayout = () => (
  <>
    <div
      className="min-h-screen font-sans flex flex-col"
      style={{
        background: `
          radial-gradient(ellipse at 4% 8%,  rgba(209,249,77,0.18) 0%, transparent 40%),
          radial-gradient(ellipse at 96% 6%,  rgba(255,182,200,0.22) 0%, transparent 38%),
          radial-gradient(ellipse at 55% 96%, rgba(200,220,255,0.14) 0%, transparent 45%),
          #f9f9f6
        `,
      }}
    >
      <header className="px-8 pt-6 pb-2">
        <Logo />
      </header>
      <Outlet />
    </div>
    <Toaster
      position="top-right"
      richColors
      closeButton
      toastOptions={{
        style: {
          background: "var(--surface-bright)",
          color: "var(--on-surface)",
          border: "1px solid var(--outline-variant)",
        },
      }}
    />
  </>
)

export default TripFlowLayout
