import { useState } from 'react';
import { updateCart } from '../lib/menu.js';

export function useCart() {
  const [cart, setCart] = useState([]);
  return {
    cart,
    add: (product) => setCart((cart) => updateCart(cart, product, 1)),
    remove: (product) => setCart((cart) => updateCart(cart, product, -1)),
    itemCount: cart.reduce((count, item) => count + item.quantity, 0),
    total: cart.reduce((total, item) => total + item.price * item.quantity, 0),
  };
}
