import { useEffect, useRef, useState } from 'react';
import { createOrderPayload } from '../lib/menu.js';
import { submitOrder } from '../services/api.js';
import { telegram } from '../services/telegram.js';

export function useCheckout(cart) {
  const [details, setDetails] = useState(() => ({
    table: new URLSearchParams(window.location.search).get('table') || '',
    name: telegram.suggestedName,
    phone: '',
  }));
  const [state, setState] = useState({ status: 'idle', error: '', orderId: '', notificationStatus: '' });
  const sending = useRef(false);
  useEffect(() => {
    if (state.status !== 'success') return;
    const timer = setTimeout(() => telegram.close(), 3000);
    return () => clearTimeout(timer);
  }, [state.status]);
  const checkout = async (event) => {
    event.preventDefault();
    if (sending.current) return;
    try {
      const payload = createOrderPayload(cart, details, telegram.userId);
      sending.current = true;
      setState({ status: 'sending', error: '', orderId: '', notificationStatus: '' });
      const order = await submitOrder(payload, telegram.initData);
      setState({ status: 'success', error: '', orderId: order.order_id, notificationStatus: order.notification_status });
    } catch (error) {
      setState({ status: 'error', error: error.message || 'Connection error. Please try again.', orderId: '', notificationStatus: '' });
    } finally {
      sending.current = false;
    }
  };
  return { ...state, details, setDetails, checkout };
}
