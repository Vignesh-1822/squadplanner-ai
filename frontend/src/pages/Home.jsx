export default function Home() {
  return (
    <div className="flex flex-col min-h-screen">
      <header className="border-b px-6 py-4 flex items-center justify-between">
        <span className="text-xl font-semibold tracking-tight">Squad Planner AI</span>
        <nav className="flex items-center gap-4 text-sm text-muted-foreground">
          <a href="#" className="hover:text-foreground transition-colors">Features</a>
          <a href="#" className="hover:text-foreground transition-colors">Pricing</a>
          <a href="/sign-in" className="hover:text-foreground transition-colors">Sign In</a>
        </nav>
      </header>
      <main className="flex-1 flex items-center justify-center">
        <p className="text-muted-foreground">Welcome to Squad Planner AI</p>
      </main>
    </div>
  )
}
