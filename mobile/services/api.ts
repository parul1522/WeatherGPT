const BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

// Pass the previous reply's session_id so follow-ups ("What about evening?") keep their context.
export const sendChat = (message: string, lang = 'en', sessionId?: string) =>
  api<{ reply: string; lang: string; session_id: string }>('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ message, lang, session_id: sessionId }),
  });

export const getWeather = (lat: number, lon: number) =>
  api(`/api/weather?lat=${lat}&lon=${lon}`);
