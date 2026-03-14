export const getNearbyStopsLabel = (charger) => {
  const windowType = (charger?.meal_window || '').toLowerCase();
  if (windowType === 'breakfast') return 'Breakfast Stops Nearby';
  if (windowType === 'coffee') return 'Coffee Stops Nearby';
  if (windowType === 'lunch') return 'Lunch Stops Nearby';
  if (windowType === 'dinner') return 'Dinner Stops Nearby';
  return 'Food Stops Nearby';
};

export const formatRoundedKm = (value) => {
  if (typeof value !== 'number' || Number.isNaN(value)) return '-';
  return `${Math.round(value)} km`;
};

export const getRankLabel = (index) => {
  if (index === 0) return 'Best overall';
  if (index === 1) return 'Strong alternative';
  if (index === 2) return 'Backup option';
  return `Option ${index + 1}`;
};
