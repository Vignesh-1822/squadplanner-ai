import { createContext, useContext, useState, useEffect } from "react"
import { getMe } from "@/services/ApiList"

const AuthContext = createContext(null)

const hasLoggedInCookie = () => {
  if (typeof document === "undefined") return false
  return document.cookie.split("; ").some((c) => c.startsWith("logged_in=true"))
}

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // If the companion cookie is not present, the user is unauthenticated.
    // Skip calling /api/auth/me to avoid unnecessary 401s on cold visits.
    if (!hasLoggedInCookie()) {
      setUser(null)
      setLoading(false)
      return
    }

    getMe()
      .then(setUser)
      .catch(() => {
        // If the token expired or was revoked, clear the stale companion cookie
        document.cookie = "logged_in=; path=/; max-age=0"
        setUser(null)
      })
      .finally(() => setLoading(false))
  }, [])

  return (
    <AuthContext.Provider value={{ user, setUser, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
