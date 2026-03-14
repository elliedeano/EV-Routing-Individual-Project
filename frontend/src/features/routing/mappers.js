export const PRIORITIES = [
  { key: 'price', label: 'Lowest Price per kWh' },
  { key: 'max_power', label: 'Highest Charging Power (kW)' },
  { key: 'is_fast', label: 'Fast Charge Capable' },
  { key: 'num_points', label: 'Most Charging Points' },
  { key: 'traffic_delay', label: 'Least Traffic Delay (% Increase)' },
];

export const PRIORITY_KEYS = new Set(PRIORITIES.map((priority) => priority.key));

export const PRIORITY_VALUE_FORMATTERS = {
  price: (value) => (typeof value === 'number' ? `£${value.toFixed(2)} / kWh` : '-'),
  max_power: (value) => (typeof value === 'number' ? `${Math.round(value)} kW` : '-'),
  is_fast: (value) => (typeof value === 'boolean' ? (value ? 'Yes' : 'No') : '-'),
  num_points: (value) => (typeof value === 'number' ? `${Math.round(value)}` : '-'),
  traffic_delay: (value) => {
    if (typeof value !== 'number') return '-';
    if (value > 0 && value < 0.1) return '<0.1%';
    return `${value.toFixed(1)}%`;
  },
};

export const PRIORITY_DIRECTIONS = {
  price: 'min',
  max_power: 'max',
  is_fast: 'max',
  num_points: 'max',
  traffic_delay: 'min',
};

export const hasValue = (value) => {
  if (value === null || value === undefined) return false;
  if (typeof value === 'string' && value.trim() === '') return false;
  if (typeof value === 'number' && Number.isNaN(value)) return false;
  return true;
};

export const toNumber = (value) => {
  if (typeof value === 'number') return value;
  if (typeof value === 'string') {
    const parsed = Number.parseFloat(value.replace(/[^\d.-]/g, ''));
    return Number.isNaN(parsed) ? NaN : parsed;
  }
  return NaN;
};

export const getPriorityScore = (charger, key) => {
  const value = charger?.[key];
  if (!hasValue(value)) return NaN;
  if (key === 'is_fast') return value ? 1 : 0;
  return typeof value === 'number' ? value : NaN;
};

export const normalizeProfile = (profile) => ({
  car_model: profile?.car_model ?? null,
  home_destination_postcode: profile?.home_destination_postcode ?? null,
  default_mode: profile?.default_mode ?? null,
  default_priorities: Array.isArray(profile?.default_priorities)
    ? profile.default_priorities.filter((key) => PRIORITY_KEYS.has(key)).slice(0, 2)
    : [],
});

export const toProfileDraft = (profile) => ({
  car_model: profile?.car_model ?? '',
  home_destination_postcode: profile?.home_destination_postcode ?? '',
  default_mode: profile?.default_mode ?? 'distance',
  default_priorities: Array.isArray(profile?.default_priorities) ? profile.default_priorities.slice(0, 2) : [],
});
