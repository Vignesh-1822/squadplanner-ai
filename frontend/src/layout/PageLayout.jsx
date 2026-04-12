import HomeHeader from "@/organisms/HomeHeader"

const PageLayout = ({ children, header = true }) => (
  <div className="flex flex-col flex-1 min-h-screen">
    {header && <HomeHeader />}
    <main className="flex-1 p-6">
      {children}
    </main>
  </div>
)

export default PageLayout
