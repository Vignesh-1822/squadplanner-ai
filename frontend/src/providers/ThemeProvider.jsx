import { createContext, useContext, useEffect, useState } from "react"

const ThemeContext = createContext(null)

// Light only for now. Pages hardcode light colours (dark text, white glass), so switching on the
// .dark tokens gives slate-grey cards under dark text. There is also no toggle in the UI, so a
// "dark" saved by an earlier one could never be switched off: it is ignored and cleared.
// To ship dark mode: design the pages for it, add a toggle, then restore reading and saving
// localStorage "theme" here.
export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState("light")

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark")
  }, [theme])

  useEffect(() => {
    try {
      localStorage.removeItem("theme")
    } catch {
      // Storage blocked (private mode, site data off): there is nothing stored to clear.
    }
  }, [])

  function toggleTheme() {
    setTheme((t) => (t === "light" ? "dark" : "light"))
  }

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  return useContext(ThemeContext)
}
