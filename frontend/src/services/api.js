import { normalizeMenu } from '../lib/menu.js';

const API_BASE_URL = (import.meta.env?.VITE_API_BASE_URL || '').replace(/\/+$/, '');
export const apiUrl = (path) => `${API_BASE_URL}${path}`;

export function mediaUrl(path) {
  if (!path || typeof path !== 'string') return '';
  if (/^https?:\/\//i.test(path)) return path;
  if (path.startsWith('/') && !path.startsWith('//')) return apiUrl(path);
  return '';
}

async function request(path, options) {
  const response = await fetch(apiUrl(path), options);
  let body;
  try { body = await response.json(); } catch { throw new Error('The server returned an invalid response. Please try again.'); }
  if (!response.ok) {
    const detail = typeof body?.detail === 'string' ? body.detail : 'Request failed. Please try again.';
    throw new Error(detail);
  }
  return body;
}

export async function fetchMenu(signal) {
  return normalizeMenu(await request('/api', { signal }));
}

export async function fetchBanner(signal) {
  const body = await request('/api/banner', { signal });
  return mediaUrl(body?.video_url);
}

export async function submitOrder(payload, initData = '') {
  const headers = { 'Content-Type': 'application/json' };
  if (initData) headers['X-Telegram-Init-Data'] = initData;
  const body = await request('/api/create_order', {
    method: 'POST', headers, body: JSON.stringify(payload),
  });
  if (body?.status !== 'ok' || !body.order_id) {
    throw new Error('The order was not confirmed. Please try again.');
  }
  return body;
}
