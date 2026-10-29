/** API 用戶端：統一錯誤格式、CSRF token、Idempotency-Key。 */

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
    public details: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

let csrfToken: string | null = null;

/** 登入、登出後 session 會更新，須重新取得 CSRF token。 */
export function resetCsrf() {
  csrfToken = null;
}

async function getCsrf(): Promise<string> {
  if (!csrfToken) {
    const res = await fetch('/api/v1/auth/csrf', { credentials: 'same-origin' });
    csrfToken = ((await res.json()) as { csrf_token: string }).csrf_token;
  }
  return csrfToken;
}

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

async function send<T>(
  method: Method,
  path: string,
  body?: unknown,
  headers: Record<string, string> = {},
  retried = false,
): Promise<T> {
  const init: RequestInit = { method, credentials: 'same-origin', headers: { ...headers } };
  const h = init.headers as Record<string, string>;
  if (method !== 'GET') h['X-CSRFToken'] = await getCsrf();
  if (body instanceof FormData) {
    init.body = body;
  } else if (body !== undefined) {
    h['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }
  const res = await fetch(`/api/v1${path}`, init);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = (
      data as { error?: { code: string; message: string; details: Record<string, unknown> } }
    ).error;
    if (res.status === 403 && err?.code === 'FORBIDDEN' && !retried && method !== 'GET') {
      resetCsrf(); // session 可能已更新，重新取得 token 重試一次
      return send<T>(method, path, body, headers, true);
    }
    throw new ApiError(
      err?.code ?? 'UNKNOWN',
      err?.message ?? '發生未知錯誤，請稍後再試',
      res.status,
      err?.details,
    );
  }
  return data as T;
}

function qs(params?: Record<string, unknown>): string {
  if (!params) return '';
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue;
    if (Array.isArray(v)) {
      if (v.length) sp.set(k, v.join(','));
    } else sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : '';
}

export const api = {
  get: <T>(path: string, params?: Record<string, unknown>) => send<T>('GET', path + qs(params)),
  post: <T>(path: string, body?: unknown, headers?: Record<string, string>) =>
    send<T>('POST', path, body ?? {}, headers),
  put: <T>(path: string, body?: unknown) => send<T>('PUT', path, body ?? {}),
  patch: <T>(path: string, body?: unknown) => send<T>('PATCH', path, body ?? {}),
  del: <T>(path: string) => send<T>('DELETE', path),
};

/** 每個「操作」產生一次；同一操作重送時沿用同一個鍵（BR-09）。 */
export const newKey = () => crypto.randomUUID();
