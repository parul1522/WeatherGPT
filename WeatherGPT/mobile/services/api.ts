const BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const sendChat = (message: string, lang = 'en') =>
  api<{ reply: string }>('/api/chat', { method: 'POST', body: JSON.stringify({ message, lang }) });

export const getWeather = (lat: number, lon: number) =>
  api(`/api/weather?lat=${lat}&lon=${lon}`);
