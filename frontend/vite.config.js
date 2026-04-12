import path from "path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [
      { find: "@/atoms",     replacement: path.resolve(__dirname, "./src/components/atoms") },
      { find: "@/molecules", replacement: path.resolve(__dirname, "./src/components/molecules") },
      { find: "@/organisms", replacement: path.resolve(__dirname, "./src/components/organisms") },
      { find: "@/templates", replacement: path.resolve(__dirname, "./src/components/templates") },
      { find: "@",           replacement: path.resolve(__dirname, "./src") },
    ],
  },
})
