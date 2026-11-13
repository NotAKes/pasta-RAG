// Telegram is optional. Never treat initDataUnsafe as authenticated identity.
export function createTelegramAdapter(host = globalThis.window) {
  const app = host?.Telegram?.WebApp;
  function call(method, ...args) {
    try { return app?.[method]?.(...args); } catch { return undefined; }
  }
  return {
    initData: typeof app?.initData === 'string' ? app.initData : '',
    suggestedName: app?.initDataUnsafe?.user?.first_name || '',
    userId: app?.initDataUnsafe?.user?.id,
    initialize() {
      call('ready');
      call('expand');
      call('setHeaderColor', '#fbf5ea');
      call('setBackgroundColor', '#fbf5ea');
    },
    openLink(url) {
      if (!app?.initData || typeof app.openLink !== 'function') return false;
      try { app.openLink(url); return true; } catch { return false; }
    },
    close() { if (app?.initData) call('close'); },
  };
}
export const telegram = createTelegramAdapter();
