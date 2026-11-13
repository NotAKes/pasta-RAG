import test from 'node:test';
import assert from 'node:assert/strict';
import { createOrderPayload, MAX_QUANTITY, normalizeMenu, updateCart } from '../src/lib/menu.js';
import { createTelegramAdapter } from '../src/services/telegram.js';

const raw = (id) => ({ id, metadata: { dish_name: 'Pasta', price: '250', image_url: '/uploads/pasta.jpg' } });
const product = normalizeMenu([raw('dish-stable')])[0];
const details = { table: ' Hotel A ', name: ' Ada ', phone: ' @ada ' };

test('menu retains stable server IDs across reordering', () => {
  assert.deepEqual(normalizeMenu([raw('b'), raw('a')]).map((item) => item.id), ['b', 'a']);
  assert.equal(product.price, 250);
});
test('menu rejects missing/duplicate identifiers and invalid prices', () => {
  for (const entries of [[raw(undefined)], [raw('a'), raw('a')], [{ ...raw('a'), metadata: { price: 'oops' } }], {}]) {
    assert.throws(() => normalizeMenu(entries));
  }
});
test('cart is immutable, caps quantity at 20 and removes zero quantities safely', () => {
  const original = [];
  let cart = original;
  for (let i = 0; i < 25; i++) cart = updateCart(cart, product, 1);
  assert.equal(cart[0].quantity, MAX_QUANTITY);
  assert.deepEqual(original, []);
  for (let i = 0; i < 25; i++) cart = updateCart(cart, product, -1);
  assert.deepEqual(cart, []);
});
test('order sends only server ID and quantity, with trimmed customer details', () => {
  const payload = createOrderPayload([{ ...product, quantity: 2 }], details);
  assert.deepEqual(payload, { table: 'Hotel A', name: 'Ada', phone: '@ada', items: [{ id: 'dish-stable', quantity: 2 }] });
  assert.equal(createOrderPayload([{ ...product, quantity: 1 }], details, 42).user_id, 42);
});
test('order validates contact, hotel, cart and quantities', () => {
  assert.throws(() => createOrderPayload([], details));
  for (const field of ['table', 'phone']) assert.throws(() => createOrderPayload([{ ...product, quantity: 1 }], { ...details, [field]: ' ' }));
  for (const quantity of [0, -1, 21, 1.5, NaN]) assert.throws(() => createOrderPayload([{ ...product, quantity }], details));
});
test('Telegram adapter supports ordinary browsers and incomplete SDKs', () => {
  const browser = createTelegramAdapter({});
  assert.equal(browser.initData, '');
  assert.equal(browser.openLink('https://example.com'), false);
  assert.doesNotThrow(() => { browser.initialize(); browser.close(); });
  const partial = createTelegramAdapter({ Telegram: { WebApp: { ready() { throw new Error('unsupported'); } } } });
  assert.doesNotThrow(() => partial.initialize());
});
test('Telegram adapter passes raw init data and only suggests unverified identity', () => {
  let opened = '';
  const adapter = createTelegramAdapter({ Telegram: { WebApp: { initData: 'signed-raw-data', initDataUnsafe: { user: { id: 42, first_name: 'Ada' } }, openLink(url) { opened = url; } } } });
  assert.equal(adapter.initData, 'signed-raw-data');
  assert.equal(adapter.suggestedName, 'Ada');
  assert.equal(adapter.openLink('https://example.com'), true);
  assert.equal(opened, 'https://example.com');
});
