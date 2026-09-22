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
      // Most routes answer with a plain string; a few (refinements) send { message, code }.
      if (typeof body.detail === "string") detail = body.detail
      else if (body.detail?.message) detail = body.detail.message
    } catch {
      // Body was not JSON — keep the status line we already built.
    }

    // The status is carried on the error rather than only in its text, so callers can branch
    // on it without string-matching a message written for humans.
    const error = new Error(detail)
    error.status = res.status
    throw error
  }

  return res.json()
}

// Export all service modules here
// export * from "./userService"
