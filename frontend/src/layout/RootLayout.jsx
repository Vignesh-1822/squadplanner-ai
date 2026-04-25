import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import SideMenu from "@/molecules/SideMenu"
import { Outlet } from "react-router-dom"
import { Toaster } from "sonner"

const RootLayout = () => (
  <>
    <div className="font-sans flex bg-gradient-halo min-h-screen">
      <SidebarProvider>
        <SideMenu />
        <SidebarInset className="overflow-x-hidden flex flex-col">
          <Outlet />
        </SidebarInset>
      </SidebarProvider>
    </div>
    <Toaster
      position="top-right"
      richColors
      closeButton
      expand
      visibleToasts={4}
      duration={4000}
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

export default RootLayout
