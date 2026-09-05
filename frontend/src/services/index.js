export const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api"

export async function apiFetch(endpoint, options = {}) {
  const res = await fetch(`${BASE_URL}${endpoint}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  })

  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body.detail) detail = body.detail
    } catch {}
    throw new Error(detail)
  }

  return res.json()
}

// Export all service modules here
// export * from "./userService"
