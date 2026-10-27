// 所有业务数据均来自同源 FastAPI；此模块不缓存名单或个人信息。
export class ApiError extends Error {
  constructor(message, { status = 0, code = 'NETWORK_ERROR', details = [] } = {}) {
    super(message);
    this.name = 'ApiError';
    Object.assign(this, { status, code, details });
  }
}

export async function api(path, { method = 'GET', body, signal } = {}) {
  const controller = new AbortController();
  let timedOut = false;
  const abort = () => controller.abort();
  if (signal?.aborted) abort();
  signal?.addEventListener('abort', abort, { once: true });
  const timer = setTimeout(() => { timedOut = true; controller.abort(); }, 15000);
  try {
    const response = await fetch(`/api${path}`, {
      method, credentials: 'same-origin', cache: 'no-store', signal: controller.signal,
      headers: { Accept: 'application/json', ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}) },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
    if (response.status === 204) return null;
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      throw new ApiError(data?.error?.message || `服务器暂时无法处理请求（${response.status}）。`, {
        status: response.status, code: data?.error?.code || 'HTTP_ERROR', details: data?.error?.details || [],
      });
    }
    if (data === null) throw new ApiError('服务器返回了无法识别的数据，请刷新重试。', { code: 'INVALID_RESPONSE' });
    return data;
  } catch (error) {
    if (signal?.aborted) throw new DOMException('Request cancelled', 'AbortError');
    if (error instanceof ApiError) throw error;
    if (timedOut) throw new ApiError(method === 'GET'
      ? '请求超时，请检查连接后重试。'
      : '请求超时，操作可能已提交。请先刷新确认结果，再决定是否重试。', { code: 'TIMEOUT' });
    throw new ApiError(method === 'GET'
      ? '无法连接服务器，请检查网络或确认后端已启动。'
      : '连接中断，操作结果尚未确认。请先刷新页面确认，再决定是否重试。');
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', abort);
  }
}

export function queryString(params) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) if (value !== '' && value != null) query.set(key, value);
  return query.toString();
}
