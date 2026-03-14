import { computeRoute } from '../services/apiClient';

export const submitRouteRequest = async (currentUser, payload) => {
  const token = await currentUser.getIdToken();
  return computeRoute(token, payload);
};
