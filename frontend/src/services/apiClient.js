const CLOUD_API_BASE = 'https://ev-routing-api-896098390327.europe-west2.run.app';
const ENV_API_BASE = import.meta.env.VITE_API_BASE || '';
const IS_LOCAL_HOST = typeof window !== 'undefined'
  && ['localhost', '127.0.0.1'].includes(window.location.hostname);

// Prefer a local backend when running the frontend on localhost.
// Priority: explicit VITE_API_BASE > localhost default > cloud production.
export const API_BASE = ENV_API_BASE || (IS_LOCAL_HOST ? 'http://127.0.0.1:8000' : CLOUD_API_BASE);

const ensureOk = async (res, fallbackMessage) => {
  if (!res.ok) {
    let detail = '';
    try {
      const data = await res.json();
      const d = data?.detail;
      if (d) {
        detail = `: ${typeof d === 'string' ? d : JSON.stringify(d)}`;
      }
    } catch (_) {
      detail = '';
    }
    throw new Error(`${fallbackMessage}${detail}`);
  }
  return res;
};

export const fetchCarModels = async (token) => {
  const res = await fetch(`${API_BASE}/api/v1/car-models`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  await ensureOk(res, 'Failed to load car models');
  return res.json();
};

export const fetchProfileDefaults = async (token) => {
  const res = await fetch(`${API_BASE}/api/v1/profile`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  await ensureOk(res, 'Failed to load profile defaults');
  return res.json();
};

export const saveProfileDefaults = async (token, payload) => {
  const res = await fetch(`${API_BASE}/api/v1/profile`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  await ensureOk(res, 'Failed to save profile defaults');
  return res.json();
};

export const computeRoute = async (token, payload) => {
  const res = await fetch(`${API_BASE}/api/v1/route`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  await ensureOk(res, 'Server error');
  return res.json();
};
