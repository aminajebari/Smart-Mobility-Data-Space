const parseBoolean = (value: string | undefined, fallback: boolean) =>
  value === undefined ? fallback : value.toLowerCase() === 'true'

export const appConfig = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api',
  useMockData: parseBoolean(import.meta.env.VITE_USE_MOCK_DATA, true),
} as const
