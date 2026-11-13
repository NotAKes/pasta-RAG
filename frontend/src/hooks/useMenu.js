import { useCallback, useEffect, useState } from 'react';
import { fetchBanner, fetchMenu } from '../services/api.js';

export function useMenu() {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState({ products: [], bannerUrl: '', loading: true, error: '' });
  useEffect(() => {
    const controller = new AbortController();
    fetchMenu(controller.signal)
      .then((products) => {
        if (!controller.signal.aborted) setState((state) => ({ ...state, products, loading: false }));
      })
      .catch((error) => {
        if (!controller.signal.aborted) setState((state) => ({ ...state, loading: false, error: error.message }));
      });
    fetchBanner(controller.signal)
      .then((bannerUrl) => {
        if (!controller.signal.aborted) setState((state) => ({ ...state, bannerUrl }));
      })
      .catch(() => {}); // A banner is optional and must not prevent ordering.
    return () => controller.abort();
  }, [attempt]);
  const retry = useCallback(() => {
    setState((state) => ({ ...state, loading: true, error: '' }));
    setAttempt((attempt) => attempt + 1);
  }, []);
  const hideBanner = useCallback(() => setState((state) => ({ ...state, bannerUrl: '' })), []);
  return { ...state, retry, hideBanner };
}
