// Thin PocketBase REST client. All requests go through the Vite /api proxy
// in development; set VITE_POCKETBASE_URL to hit PocketBase directly.

const BASE = import.meta.env.VITE_POCKETBASE_URL || '';
const TOKEN_KEY = 'astra_token';
const RECORD_KEY = 'astra_record';

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getRecord() {
  try {
    return JSON.parse(localStorage.getItem(RECORD_KEY));
  } catch {
    return null;
  }
}

export function isLoggedIn() {
  return Boolean(getToken());
}

export async function login(identity, password) {
  const response = await fetch(`${BASE}/api/collections/astronauts/auth-with-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ identity, password }),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.message || 'Login failed');
  }
  localStorage.setItem(TOKEN_KEY, data.token);
  localStorage.setItem(RECORD_KEY, JSON.stringify(data.record));
  return data.record;
}

export function logout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(RECORD_KEY);
}

export async function api(path, { method = 'GET', body, query } = {}) {
  const suffix = query ? '?' + new URLSearchParams(query).toString() : '';
  const response = await fetch(`${BASE}/api${path}${suffix}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(getToken() ? { Authorization: getToken() } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.message || `Request failed (${response.status})`);
  }
  return data;
}

export async function listRecords(collection, { filter, sort, perPage = 100, page = 1, fields } = {}) {
  const query = { perPage, page, skipTotal: 'true' };
  if (filter) query.filter = filter;
  if (sort) query.sort = sort;
  if (fields) query.fields = fields;
  const data = await api(`/collections/${collection}/records`, { query });
  return data.items || [];
}
