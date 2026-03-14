import { normalizeProfile, toProfileDraft } from '../features/routing/mappers';
import { fetchProfileDefaults, saveProfileDefaults } from '../services/apiClient';

export const loadProfileDefaults = async (currentUser) => {
  if (!currentUser) return null;
  const token = await currentUser.getIdToken();
  const raw = await fetchProfileDefaults(token);
  return normalizeProfile(raw);
};

export const persistProfileDefaults = async (currentUser, payload) => {
  const token = await currentUser.getIdToken();
  const raw = await saveProfileDefaults(token, payload);
  return normalizeProfile(raw);
};

export { toProfileDraft };
