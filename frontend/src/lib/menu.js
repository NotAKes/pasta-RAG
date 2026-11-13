export const MAX_QUANTITY = 20;

export function normalizeMenu(entries) {
  if (!Array.isArray(entries)) throw new Error('Invalid menu response. Please try again.');
  const ids = new Set();
  return entries.map((entry) => {
    if (typeof entry?.id !== 'string' || !entry.id.trim() || ids.has(entry.id)) {
      throw new Error('Menu identifiers are unavailable. Please try again later.');
    }
    ids.add(entry.id);
    const price = Number(entry.metadata?.price);
    if (!Number.isFinite(price) || price < 0) throw new Error('Invalid menu price. Please try again later.');
    return {
      id: entry.id,
      name: entry.metadata?.dish_name || 'Unknown Dish',
      price,
      description: entry.text || '',
      image_url: entry.metadata?.image_url || '',
    };
  });
}

export function updateCart(cart, product, change) {
  const existing = cart.find((item) => item.id === product.id);
  const quantity = Math.max(0, Math.min(MAX_QUANTITY, (existing?.quantity || 0) + change));
  if (!quantity) return cart.filter((item) => item.id !== product.id);
  if (!existing) return [...cart, { ...product, quantity }];
  return cart.map((item) => item.id === product.id ? { ...item, quantity } : item);
}

export function createOrderPayload(cart, details, userId) {
  if (!cart.length) throw new Error('Please add a dish to your order.');
  if (!details.table.trim()) throw new Error('Please enter your hotel or table number.');
  if (!details.phone.trim()) throw new Error('Please leave a phone, Telegram, or WhatsApp contact.');
  const payload = {
    table: details.table.trim(),
    name: details.name.trim() || 'Guest',
    phone: details.phone.trim(),
    items: cart.map(({ id, quantity }) => {
      if (typeof id !== 'string' || !id || !Number.isInteger(quantity) || quantity < 1 || quantity > MAX_QUANTITY) {
        throw new Error('Invalid cart quantity. Please update your order.');
      }
      return { id, quantity };
    }),
  };
  if (userId != null) payload.user_id = userId; // A hint only; the server verifies Telegram identity.
  return payload;
}
