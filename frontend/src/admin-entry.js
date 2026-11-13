import { apiUrl, mediaUrl } from './services/api.js';

// Classic public script preserves existing inline handlers; this entry supplies Vite configuration.
if (typeof window.initializeAdmin === 'function') {
  window.initializeAdmin({ apiBaseUrl: apiUrl(''), mediaUrl });
} else {
  document.getElementById('loginError').textContent = 'Unable to load the admin panel. Please reload to retry.';
}
