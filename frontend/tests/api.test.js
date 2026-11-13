import test from 'node:test';
import assert from 'node:assert/strict';
import { apiUrl, mediaUrl, submitOrder } from '../src/services/api.js';

test('API defaults to same-origin and only resolves safe media URLs', () => {
  assert.equal(apiUrl('/api'), '/api');
  assert.equal(mediaUrl('/uploads/pasta.jpg'), '/uploads/pasta.jpg');
  assert.equal(mediaUrl('https://cdn.example/pasta.jpg'), 'https://cdn.example/pasta.jpg');
  assert.equal(mediaUrl('javascript:alert(1)'), '');
  assert.equal(mediaUrl('//untrusted.example/image'), '');
});
test('orders send Telegram init data header, never a shared secret', async (t) => {
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, '/api/create_order');
    assert.equal(options.headers['X-Telegram-Init-Data'], 'signed');
    assert.equal(options.headers['X-Secret-Token'], undefined);
    return { ok: true, json: async () => ({ status: 'ok', order_id: 'order-1' }) };
  });
  assert.equal((await submitOrder({ items: [] }, 'signed')).order_id, 'order-1');
});
test('orders require HTTP success, body success, and an order reference', async (t) => {
  for (const [ok, body] of [[false, { detail: 'Denied' }], [true, { status: 'error' }], [true, { status: 'ok' }]]) {
    const mock = t.mock.method(globalThis, 'fetch', async () => ({ ok, json: async () => body }));
    await assert.rejects(submitOrder({}));
    mock.mock.restore();
  }
});
test('orders handle malformed JSON and network failures', async (t) => {
  let mock = t.mock.method(globalThis, 'fetch', async () => ({ ok: true, json: async () => { throw new SyntaxError(); } }));
  await assert.rejects(submitOrder({}), /invalid response/);
  mock.mock.restore();
  mock = t.mock.method(globalThis, 'fetch', async () => { throw new Error('offline'); });
  await assert.rejects(submitOrder({}), /offline/);
});
