import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { GoogleOAuthProvider, GoogleLogin } from "@react-oauth/google"
import { Eye, EyeOff, Zap, Users, Quote } from "lucide-react"
import { register, login, googleAuth } from "@/services/ApiList"
import { useAuth } from "@/store/authStore.jsx"
import { PENDING_INVITE_KEY } from "@/pages/JoinTrip"

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? ""

export default function Auth() {
  const navigate = useNavigate()
  const { user, loading, setUser } = useAuth()

  // A guest who arrived from an invite link is returned to it after signing in, rather than
  // being dropped on the home page with their invite lost.
  const afterAuth = () => {
    const pending = sessionStorage.getItem(PENDING_INVITE_KEY)
    navigate(pending ? `/join/${pending}` : "/")
  }

  useEffect(() => {
    if (!loading && user) {
      afterAuth()
    }
  }, [user, loading])

  const [mode, setMode] = useState("login") // "login" | "register"
  const [showPw, setShowPw] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState("")

  const [form, setForm] = useState({ firstName: "", lastName: "", email: "", password: "" })
  const patch = (field) => (e) => setForm((p) => ({ ...p, [field]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError("")
    setIsLoading(true)
    try {
      const data = mode === "register"
        ? await register({ name: `${form.firstName} ${form.lastName}`.trim(), email: form.email, password: form.password })
        : await login({ email: form.email, password: form.password })
      setUser(data)
      afterAuth()
    } catch (err) {
      // The backend writes these for users — "Email already registered", "Invalid email or
      // password" — so they are shown as-is rather than flattened to one guess.
      setError(err.message || "Something went wrong. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  const handleGoogle = async (credentialResponse) => {
    setError("")
    setIsLoading(true)
    try {
      const data = await googleAuth({ token: credentialResponse.credential })
      setUser(data)
      afterAuth()
    } catch (err) {
      setError(err.message ?? "Google sign-in failed. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  const handleGetStarted = () => {
    setMode("register")
    const formElement = document.getElementById("auth-card")
    if (formElement) {
      formElement.scrollIntoView({ behavior: "smooth" })
    }
  }

  if (loading || user) return null

  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <div
        className="min-h-screen lg:h-screen lg:overflow-hidden text-slate-900 antialiased flex flex-col justify-between"
        style={{
          background: 'radial-gradient(circle at top left, #f0fff4 0%, #f8f8f5 40%, #fdfcf0 100%)'
        }}
      >
        {/* TopAppBar */}
        <header className="fixed top-0 left-0 right-0 z-50 bg-white/70 backdrop-blur-xl border-b border-slate-200/50 shadow-sm shadow-[#d1f94d]/5">
          <div className="flex justify-between items-center px-6 py-3.5 w-full max-w-7xl mx-auto">
            <div className="flex items-center gap-2">
              <span className="text-xl font-black text-slate-900 uppercase tracking-tighter">SquadPlanner</span>
            </div>
            <div className="hidden md:flex items-center gap-6">
              <a className="text-slate-500 text-sm font-bold hover:bg-[#d1f94d]/20 transition-colors px-3 py-1 rounded-lg" href="#">Product</a>
              <a className="text-slate-500 text-sm font-bold hover:bg-[#d1f94d]/20 transition-colors px-3 py-1 rounded-lg" href="#">Community</a>
              <a className="text-slate-500 text-sm font-bold hover:bg-[#d1f94d]/20 transition-colors px-3 py-1 rounded-lg" href="#">Pricing</a>
            </div>
            <button
              onClick={handleGetStarted}
              className="bg-primary text-on-primary font-black px-5 py-1.5 rounded-lg scale-95 active:scale-90 transition-all duration-300 uppercase text-[0.7rem] tracking-widest volt-glow"
            >
              Get Started
            </button>
          </div>
        </header>

        {/* Main Content */}
        <main className="pt-20 pb-8 px-6 max-w-7xl mx-auto w-full flex-grow flex flex-col justify-center overflow-y-auto lg:overflow-visible">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">

            {/* Left Column: Value Props */}
            <div className="lg:col-span-5 space-y-8">
              <div className="space-y-4">
                <h1 className="text-5xl md:text-6xl font-black text-slate-900 tracking-tighter leading-none">
                  Design your <span className="bg-primary px-2">Legacy</span>
                </h1>
                <p className="text-slate-600 text-md max-w-md">
                  The elite hub for high-performance squads to synchronize, strategize, and scale. Join the movement of Kinetic Serenity.
                </p>
              </div>

              <div className="grid grid-cols-1 gap-4">
                {/* Stat Card 1 */}
                <div className="glass-card p-6 rounded-xl flex items-center gap-6 group hover:translate-x-2 transition-transform duration-300">
                  <div className="bg-primary p-3 rounded-lg text-on-primary">
                    <Users className="w-8 h-8" />
                  </div>
                  <div>
                    <div className="text-2xl font-black text-slate-900">12k+</div>
                    <div className="text-[0.75rem] font-bold uppercase tracking-widest text-slate-500">Active Squads</div>
                  </div>
                </div>

                {/* Stat Card 2 */}
                <div className="glass-card p-6 rounded-xl flex items-center gap-6 group hover:translate-x-2 transition-transform duration-300">
                  <div className="bg-[#334155] p-3 rounded-lg text-primary">
                    <Zap className="w-8 h-8" />
                  </div>
                  <div>
                    <div className="text-2xl font-black text-slate-900">Real-Time</div>
                    <div className="text-[0.75rem] font-bold uppercase tracking-widest text-slate-500">Kinetic Syncing</div>
                  </div>
                </div>

                {/* Testimonial Small */}
                <div className="glass-card p-6 rounded-xl relative overflow-hidden">
                  <div className="relative z-10">
                    <p className="text-slate-900 font-bold italic mb-2">
                      &quot;The only platform that understands the pulse of modern digital coordination.&quot;
                    </p>
                    <div className="flex items-center gap-3">
                      {/* Initials rather than a photo: the old image was a temporary Stitch export URL
                          that would stop loading, and it loaded from Google on every visit. */}
                      <div
                        aria-hidden="true"
                        className="w-8 h-8 rounded-full bg-slate-900 text-primary text-[0.7rem] font-black flex items-center justify-center"
                      >
                        AR
                      </div>
                      <span className="text-[0.75rem] font-bold uppercase tracking-widest text-slate-500">
                        Alex Reed, Lead Architect
                      </span>
                    </div>
                  </div>
                  <div className="absolute -right-4 -bottom-4 opacity-10">
                    <Quote className="w-24 h-24 text-slate-900" />
                  </div>
                </div>
              </div>
            </div>

            {/* Right Column: Authentication Card */}
            <div className="lg:col-span-7 flex justify-center lg:justify-end" id="auth-card">
              <div className="glass-card w-full max-w-lg p-6 md:p-8 rounded-2xl shadow-xl relative overflow-hidden">
                {/* Decor Pulse */}
                <div className="absolute -top-6 -right-6 w-20 h-20 bg-primary/20 blur-3xl rounded-full animate-pulse"></div>

                <div className="text-center mb-6">
                  <h2 className="text-2xl font-black text-slate-900 mb-1">
                    {mode === "login" ? "Welcome back" : "Create your account"}
                  </h2>
                  <p className="text-slate-500 text-xs">
                    {mode === "login"
                      ? "Sign in to continue planning."
                      : "Join the next generation of squad management."}
                  </p>
                </div>

                <div className="space-y-4">
                  {/* Google OAuth Action */}
                  <div className="google-login-wrapper w-full shadow-sm">
                    <GoogleLogin
                      onSuccess={handleGoogle}
                      onError={() => setError("Google sign-in failed.")}
                      theme="outline"
                      shape="rectangular"
                      size="large"
                      text={mode === "login" ? "signin_with" : "signup_with"}
                      width="100%"
                    />
                  </div>

                  <div className="relative flex items-center py-2">
                    <div className="flex-grow border-t border-slate-200"></div>
                    <span className="flex-shrink mx-3 text-[0.65rem] font-bold uppercase tracking-widest text-slate-500">
                      Or continue with email
                    </span>
                    <div className="flex-grow border-t border-slate-200"></div>
                  </div>

                  {/* Error Alert */}
                  {error && (
                    <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-600 text-xs">
                      {error}
                    </div>
                  )}

                  {/* Email Form */}
                  <form className="space-y-3" onSubmit={handleSubmit}>
                    {mode === "register" && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div className="space-y-1">
                          <label className="text-[0.65rem] font-bold uppercase tracking-widest text-slate-500 px-1">First Name</label>
                          <input
                            className="w-full bg-[#f0fff4] border-none rounded-xl p-3 text-sm focus:ring-2 focus:ring-primary text-slate-900 outline-none"
                            placeholder="Leon"
                            type="text"
                            value={form.firstName}
                            onChange={patch("firstName")}
                            required
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-[0.65rem] font-bold uppercase tracking-widest text-slate-500 px-1">Last Name</label>
                          <input
                            className="w-full bg-[#f0fff4] border-none rounded-xl p-3 text-sm focus:ring-2 focus:ring-primary text-slate-900 outline-none"
                            placeholder="Curator"
                            type="text"
                            value={form.lastName}
                            onChange={patch("lastName")}
                            required
                          />
                        </div>
                      </div>
                    )}

                    <div className="space-y-1">
                      <label className="text-[0.65rem] font-bold uppercase tracking-widest text-slate-500 px-1">Email Address</label>
                      <input
                        className="w-full bg-[#f0fff4] border-none rounded-xl p-3 text-sm focus:ring-2 focus:ring-primary text-slate-900 outline-none"
                        placeholder="curator@squad.com"
                        type="email"
                        value={form.email}
                        onChange={patch("email")}
                        required
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="text-[0.65rem] font-bold uppercase tracking-widest text-slate-500 px-1">Password</label>
                      <div className="relative">
                        <input
                          className="w-full bg-[#f0fff4] border-none rounded-xl p-3 text-sm focus:ring-2 focus:ring-primary text-slate-900 outline-none pr-10"
                          placeholder="••••••••"
                          type={showPw ? "text" : "password"}
                          value={form.password}
                          onChange={patch("password")}
                          required
                          minLength={8}
                        />
                        <button
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-700"
                          type="button"
                          onClick={() => setShowPw((v) => !v)}
                        >
                          {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                      </div>
                    </div>

                    <div className="pt-2">
                      <button
                        type="submit"
                        disabled={isLoading}
                        className="w-full bg-slate-950 text-primary font-black p-3.5 rounded-xl hover:scale-[1.01] active:scale-95 transition-all duration-300 uppercase tracking-widest text-xs volt-glow disabled:opacity-50"
                      >
                        {isLoading ? "Please wait..." : mode === "login" ? "Sign In" : "Initialize Account"}
                      </button>
                    </div>
                  </form>

                  <p className="text-center text-slate-500 text-xs mt-4">
                    {mode === "login" ? "Don't have an account? " : "Already have an account? "}
                    <button
                      type="button"
                      onClick={() => { setMode(mode === "login" ? "register" : "login"); setError("") }}
                      className="text-slate-900 font-black underline decoration-primary decoration-4 hover:text-primary transition-colors"
                    >
                      {mode === "login" ? "Sign Up" : "Log In"}
                    </button>
                  </p>
                </div>
              </div>
            </div>

          </div>
        </main>

        {/* Footer */}
        <footer className="bg-slate-50 border-t border-slate-100 py-5 w-full mt-auto">
          <div className="flex flex-col md:flex-row justify-between items-center px-8 w-full max-w-7xl mx-auto space-y-4 md:space-y-0">
            <div className="text-[0.65rem] font-bold uppercase tracking-widest text-slate-500">
              © 2024 SquadPlanner. Built for Kinetic Serenity.
            </div>
            <div className="flex gap-6">
              <a className="text-[0.65rem] font-bold uppercase tracking-widest text-slate-500 hover:text-[#d1f94d] transition-colors opacity-80 hover:opacity-100" href="#">Privacy Policy</a>
              <a className="text-[0.65rem] font-bold uppercase tracking-widest text-slate-500 hover:text-[#d1f94d] transition-colors opacity-80 hover:opacity-100" href="#">Terms of Service</a>
              <a className="text-[0.65rem] font-bold uppercase tracking-widest text-slate-500 hover:text-[#d1f94d] transition-colors opacity-80 hover:opacity-100" href="#">System Status</a>
            </div>
          </div>
        </footer>

      </div>
    </GoogleOAuthProvider>
  )
}
