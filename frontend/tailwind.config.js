/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        /* Core */
        primary: {
          DEFAULT:   "var(--primary)",
          dim:       "var(--primary-dim)",
          container: "var(--primary-container)",
        },
        secondary: {
          DEFAULT:   "var(--secondary)",
          container: "var(--secondary-container)",
          "on-container": "var(--on-secondary-container)",
        },
        tertiary: {
          DEFAULT:   "var(--tertiary)",
          container: "var(--tertiary-container)",
        },
        /* On-colors — standalone so text-on-primary etc. work */
        "on-primary":   "var(--on-primary)",
        "on-secondary": "var(--on-secondary)",
        "on-tertiary":  "var(--on-tertiary)",
        "on-surface":   "var(--on-surface)",
        /* Surfaces */
        background:  "var(--background)",
        surface: {
          DEFAULT:  "var(--surface)",
          bright:   "var(--surface-bright)",
          dim:      "var(--surface-dim)",
          low:      "var(--surface-container-low)",
          container:"var(--surface-container)",
          high:     "var(--surface-container-high)",
          highest:  "var(--surface-container-highest)",
          variant:  "var(--surface-variant)",
        },
        /* Text */
        foreground:  "var(--on-surface)",
        "on-surface-variant": "var(--on-surface-variant)",
        /* Functional */
        border:      "var(--border)",
        input:       "var(--input)",
        ring:        "var(--ring)",
        muted: {
          DEFAULT:   "var(--muted)",
          foreground:"var(--muted-foreground)",
        },
        accent: {
          DEFAULT:   "var(--accent)",
          foreground:"var(--accent-foreground)",
        },
        destructive: "var(--destructive)",
        error: {
          DEFAULT:   "var(--error)",
          container: "var(--error-container)",
        },
        /* Outline */
        outline: {
          DEFAULT: "var(--outline)",
          variant: "var(--outline-variant)",
        },
      },
      borderRadius: {
        sm:   "var(--radius-sm)",
        DEFAULT: "var(--radius-md)",
        md:   "var(--radius-md)",
        lg:   "var(--radius-lg)",
        full: "var(--radius-full)",
      },
      boxShadow: {
        volt:  "var(--shadow-volt)",
        slate: "var(--shadow-slate)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
}
