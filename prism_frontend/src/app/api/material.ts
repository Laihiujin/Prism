
const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_BASE || "http://localhost:7000"

async function request<T>(path: string, options?: RequestInit) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    cache: "no-store",
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Request failed with ${response.status}`)
  }
  const data = (await response.json()) as T
  return { data }
}

export const materialApi = {
  getAllMaterials: () => request<{ total: number; items: unknown[] }>("/api/v1/files/"),
  uploadMaterial: (formData: FormData) =>
    request("/api/v1/files/upload-save", {
      method: "POST",
      body: formData,
    }),
  deleteMaterial: (id: string) => request(`/api/v1/files/${encodeURIComponent(id)}`, { method: "DELETE" }),
  getMaterialPreviewUrl: (filename: string) => `${API_BASE_URL}/api/v1/files/${filename}`,
}
