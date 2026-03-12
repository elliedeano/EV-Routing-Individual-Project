import { useEffect, useMemo, useState } from 'react';
import {
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signOut,
} from 'firebase/auth';
import { auth, authInitError } from './firebase';

const CLOUD_API_BASE = 'https://ev-routing-api-896098390327.europe-west2.run.app';
const ENV_API_BASE = import.meta.env.VITE_API_BASE || '';
const IS_LOCAL_HOST = typeof window !== 'undefined'
  && ['localhost', '127.0.0.1'].includes(window.location.hostname);
const API_BASE = (!IS_LOCAL_HOST && ENV_API_BASE.includes('localhost'))
  ? CLOUD_API_BASE
  : (ENV_API_BASE || CLOUD_API_BASE);

const PRIORITIES = [
  { key: 'price', label: 'Lowest Price per kWh' },
  { key: 'max_power', label: 'Highest Charging Power (kW)' },
  { key: 'is_fast', label: 'Fast Charge Capable' },
  { key: 'num_points', label: 'Most Charging Points' },
  { key: 'distance', label: 'Closest Distance' },
  { key: 'traffic_delay', label: 'Least Traffic Delay (% Increase)' },
];

const PRIORITY_VALUE_FORMATTERS = {
  price: (value) => (typeof value === 'number' ? `£${value.toFixed(2)} / kWh` : '-'),
  max_power: (value) => (typeof value === 'number' ? `${Math.round(value)} kW` : '-'),
  is_fast: (value) => (typeof value === 'boolean' ? (value ? 'Yes' : 'No') : '-'),
  num_points: (value) => (typeof value === 'number' ? `${Math.round(value)}` : '-'),
  distance: (value) => (typeof value === 'number' ? `${Math.round(value)} km` : '-'),
  traffic_delay: (value) => {
    if (typeof value !== 'number') return '-';
    if (value > 0 && value < 0.1) return '<0.1%';
    return `${value.toFixed(1)}%`;
  },
};

const hasValue = (value) => {
  if (value === null || value === undefined) return false;
  if (typeof value === 'string' && value.trim() === '') return false;
  if (typeof value === 'number' && Number.isNaN(value)) return false;
  return true;
};

const toNumber = (value) => {
  if (typeof value === 'number') return value;
  if (typeof value === 'string') {
    const parsed = Number.parseFloat(value.replace(/[^\d.-]/g, ''));
    return Number.isNaN(parsed) ? NaN : parsed;
  }
  return NaN;
};


const PRIORITY_DIRECTIONS = {
  price: 'min',
  max_power: 'max',
  is_fast: 'max',
  num_points: 'max',
  distance: 'min',
  traffic_delay: 'min',
};

const getPriorityScore = (charger, key) => {
  const value = charger?.[key];
  if (!hasValue(value)) return NaN;
  if (key === 'is_fast') return value ? 1 : 0;
  return typeof value === 'number' ? value : NaN;
};

export default function App() {
  const [authReady, setAuthReady] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  const [authMode, setAuthMode] = useState('login');
  const [authForm, setAuthForm] = useState({ email: '', password: '' });
  const [authError, setAuthError] = useState(null);

  const [models, setModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [modelsError, setModelsError] = useState(null);

  const [form, setForm] = useState({
    journeyStartMode: 'now',
    journeyTime: '',
    start_postcode: '',
    end_postcode: '',
    soc: '',
    car_model: '',
    umbrella_choice: 'distance',
  });
  const [selectedPriorities, setSelectedPriorities] = useState([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [profileStatus, setProfileStatus] = useState(null);

  useEffect(() => {
    if (!auth) {
      setAuthReady(true);
      return undefined;
    }
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      setCurrentUser(user || null);
      setAuthReady(true);
    });
    return () => unsubscribe();
  }, []);

  useEffect(() => {
    if (!currentUser) {
      setModels([]);
      setLoadingModels(false);
      return undefined;
    }

    let cancelled = false;
    setLoadingModels(true);
    currentUser.getIdToken()
      .then((token) => fetch(`${API_BASE}/api/v1/car-models`, {
        headers: { Authorization: `Bearer ${token}` },
      }))
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load car models');
        return res.json();
      })
      .then((data) => {
        if (!cancelled) setModels(data.models || []);
      })
      .catch((err) => {
        if (!cancelled) setModelsError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoadingModels(false);
      });
    return () => {
      cancelled = true;
    };
  }, [currentUser]);

  const umbrellaPriority = useMemo(() => {
    return form.umbrella_choice === 'meal' ? 'meal_stop' : 'distance_stop';
  }, [form.umbrella_choice]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleNowClick = () => {
    setForm((prev) => ({ ...prev, journeyStartMode: 'now', journeyTime: '' }));
  };

  const handleJourneyTimeChange = (e) => {
    const { value } = e.target;
    setForm((prev) => ({ ...prev, journeyTime: value, journeyStartMode: value ? 'time' : 'now' }));
  };

  const handleModeSelect = (mode) => {
    setForm((prev) => ({ ...prev, umbrella_choice: mode }));
  };

  const handleAuthFormChange = (e) => {
    const { name, value } = e.target;
    setAuthForm((prev) => ({ ...prev, [name]: value }));
  };

  const getFriendlyAuthError = (err) => {
    const code = err?.code || '';
    if (code === 'auth/configuration-not-found') {
      return 'Firebase Authentication is not enabled for this project yet.';
    }
    if (code === 'auth/invalid-api-key') {
      return 'Invalid Firebase API key. Check your frontend/.env values.';
    }
    if (code === 'auth/email-already-in-use') {
      return 'This email is already in use. Try signing in instead.';
    }
    if (code === 'auth/invalid-credential' || code === 'auth/user-not-found' || code === 'auth/wrong-password') {
      return 'Invalid email or password.';
    }
    return err?.message || 'Authentication failed';
  };

  const handleAuthSubmit = async (e) => {
    e.preventDefault();
    setAuthError(null);
    try {
      if (authMode === 'signup') {
        await createUserWithEmailAndPassword(auth, authForm.email.trim(), authForm.password);
      } else {
        await signInWithEmailAndPassword(auth, authForm.email.trim(), authForm.password);
      }
      setAuthForm((prev) => ({ ...prev, password: '' }));
    } catch (err) {
      setAuthError(getFriendlyAuthError(err));
    }
  };

  const handleLogout = async () => {
    await signOut(auth);
    setResult(null);
    setSelectedPriorities([]);
    setProfileStatus(null);
    setError(null);
  };

  const saveProfileDefaults = async () => {
    if (!currentUser) return;
    try {
      setProfileStatus('Saving defaults...');
      const token = await currentUser.getIdToken();
      const payload = {
        car_model: form.car_model || null,
        home_destination_postcode: form.end_postcode.trim() || null,
        default_mode: form.umbrella_choice || 'distance',
        default_priorities: selectedPriorities,
      };
      const res = await fetch(`${API_BASE}/api/v1/profile`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error('Failed to save profile defaults');
      setProfileStatus('Defaults saved.');
    } catch (err) {
      setProfileStatus(err.message || 'Failed to save defaults');
    }
  };

  const loadProfileDefaults = async () => {
    if (!currentUser) return;
    try {
      setProfileStatus('Loading defaults...');
      const token = await currentUser.getIdToken();
      const res = await fetch(`${API_BASE}/api/v1/profile`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Failed to load profile defaults');
      const profile = await res.json();

      setForm((prev) => ({
        ...prev,
        car_model: profile?.car_model || prev.car_model,
        end_postcode: profile?.home_destination_postcode || prev.end_postcode,
        umbrella_choice: profile?.default_mode || prev.umbrella_choice,
      }));
      if (Array.isArray(profile?.default_priorities)) {
        setSelectedPriorities(profile.default_priorities.slice(0, 2));
      }
      setProfileStatus('Defaults loaded.');
    } catch (err) {
      setProfileStatus(err.message || 'Failed to load defaults');
    }
  };

  const togglePriority = (key) => {
    setSelectedPriorities((prev) => {
      if (prev.includes(key)) {
        return prev.filter((p) => p !== key);
      }
      if (prev.length >= 2) return prev;
      return [...prev, key];
    });
  };

  const journey_start = form.journeyStartMode === 'now'
    ? 'now'
    : form.journeyTime;

  const getRankLabel = (index) => {
    if (index === 0) return 'Best overall';
    if (index === 1) return 'Strong alternative';
    if (index === 2) return 'Backup option';
    return `Option ${index + 1}`;
  };

  const formatRoundedKm = (value) => {
    if (typeof value !== 'number' || Number.isNaN(value)) return '-';
    return `${Math.round(value)} km`;
  };

  const getNearbyStopsLabel = (charger) => {
    const windowType = (charger?.meal_window || '').toLowerCase();
    if (windowType === 'breakfast') return 'Breakfast Stops Nearby';
    if (windowType === 'coffee') return 'Coffee Stops Nearby';
    if (windowType === 'lunch') return 'Lunch Stops Nearby';
    if (windowType === 'dinner') return 'Dinner Stops Nearby';
    return 'Food Stops Nearby';
  };

  const getSelectedPriorityDetails = (charger) => {
    return selectedPriorities.map((key) => {
      const priority = PRIORITIES.find((p) => p.key === key);
      const formatter = PRIORITY_VALUE_FORMATTERS[key] || ((value) => value ?? '-');
      const rawValue = charger?.[key];
      return {
        key,
        label: priority?.label || key,
        value: hasValue(rawValue) ? formatter(rawValue) : null,
      };
    }).filter((item) => hasValue(item.value));
  };

  const getTopChargerReason = (charger) => {
    const reasons = [];
    if (form.umbrella_choice === 'meal' && charger?.meal_stop === true) {
      reasons.push('it matches your meal-based mode');
    }
    if (form.umbrella_choice === 'distance' && charger?.meal_stop === false) {
      reasons.push('it matches your distance-based mode');
    }

    const selectedDetails = getSelectedPriorityDetails(charger);
    if (selectedDetails.length > 0) {
      const priorityNames = selectedDetails.map((item) => item.label.toLowerCase());
      reasons.push(`strong on ${priorityNames.join(' and ')}`);
    }

    if (reasons.length === 0) {
      return 'Best match for your trip.';
    }

    return `Best match for your trip — ${reasons.join(', ')}.`;
  };

  const bestPriorityScores = useMemo(() => {
    const chargers = Array.isArray(result?.chargers) ? result.chargers : [];
    const out = {};
    for (const key of selectedPriorities) {
      const direction = PRIORITY_DIRECTIONS[key] || 'max';
      const scores = chargers.map((charger) => getPriorityScore(charger, key));
      const hasMissingValues = scores.some((score) => Number.isNaN(score));
      if (hasMissingValues) continue;
      out[key] = direction === 'min' ? Math.min(...scores) : Math.max(...scores);
    }
    return out;
  }, [result, selectedPriorities]);

  const isBestForPriority = (charger, key) => {
    const bestScore = bestPriorityScores[key];
    if (typeof bestScore !== 'number' || Number.isNaN(bestScore)) return false;
    const score = getPriorityScore(charger, key);
    if (Number.isNaN(score)) return false;
    return score === bestScore;
  };

  const noChargingNeeded = result && toNumber(result.est_range_km) >= toNumber(result.total_km);
  const showMealFallbackNotice = (
    form.umbrella_choice === 'meal'
    && !!result
    && !noChargingNeeded
    && Array.isArray(result.chargers)
    && result.chargers.length > 0
    && !result.chargers.some((charger) => charger?.meal_stop)
  );

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!currentUser) {
      setError('Please log in first.');
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const token = await currentUser.getIdToken();
      const priorities = [umbrellaPriority, ...selectedPriorities];
      const payload = {
        start_postcode: form.start_postcode.trim(),
        end_postcode: form.end_postcode.trim(),
        soc: Number(form.soc),
        car_model: form.car_model || null,
        umbrella_choice: form.umbrella_choice,
        meal_window: null,
        priorities,
        journey_start,
      };
      const res = await fetch(`${API_BASE}/api/v1/route`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error('Server error');
      const data = await res.json();
      setResult(data);
    } catch (err) {
      setError(err.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  if (!authReady) {
    return (
      <main className="page">
        <header className="header">
          <h1>EV Charger Planner</h1>
        </header>
        <div className="layout">
          <section className="panel">
            <div className="card section-card">
              <p className="hint">Loading authentication...</p>
            </div>
          </section>
        </div>
      </main>
    );
  }

  if (authInitError) {
    return (
      <main className="page">
        <header className="header">
          <h1>EV Charger Planner</h1>
        </header>
        <div className="layout">
          <section className="panel">
            <div className="card section-card">
              <h2>Firebase setup error</h2>
              <p className="error">{authInitError}</p>
              <p className="hint">Check frontend/.env Firebase values and restart npm run dev.</p>
            </div>
          </section>
        </div>
      </main>
    );
  }

  if (!currentUser) {
    return (
      <main className="page">
        <header className="header">
          <h1>EV Charger Planner</h1>
        </header>
        <div className="layout">
          <section className="panel">
            <div className="card section-card">
              <h2>{authMode === 'signup' ? 'Create account' : 'Sign in'}</h2>
              <form className="grid" onSubmit={handleAuthSubmit}>
                <label>
                  Email
                  <input
                    name="email"
                    type="email"
                    value={authForm.email}
                    onChange={handleAuthFormChange}
                    required
                  />
                </label>
                <label>
                  Password
                  <input
                    name="password"
                    type="password"
                    value={authForm.password}
                    onChange={handleAuthFormChange}
                    minLength={6}
                    required
                  />
                </label>
                <div className="actions">
                  <button type="submit">{authMode === 'signup' ? 'Create account' : 'Sign in'}</button>
                  <button
                    type="button"
                    onClick={() => {
                      setAuthMode((prev) => (prev === 'signup' ? 'login' : 'signup'));
                      setAuthError(null);
                    }}
                  >
                    {authMode === 'signup' ? 'Use sign in' : 'Create account instead'}
                  </button>
                </div>
                {authError && <p className="error">{authError}</p>}
                {authError === 'Firebase Authentication is not enabled for this project yet.' && (
                  <p className="hint">
                    In Firebase Console: Build → Authentication → Get started, then enable Email/Password.
                  </p>
                )}
              </form>
            </div>
          </section>
        </div>
      </main>
    );
  }

  return (
    <main className="page">
      <header className="header">
        <h1>EV Charger Planner</h1>
        <p className="hint">Signed in as {currentUser.email}</p>
      </header>

      <div className="layout">
        <form className="panel" onSubmit={handleSubmit}>
          <section className="card section-card">
            <h2>Journey Time</h2>
            <div className="row">
              <button
                type="button"
                className={`now-btn ${form.journeyStartMode === 'now' ? 'now-btn--active' : ''}`}
                onClick={handleNowClick}
              >
                <span className={`now-indicator ${form.journeyStartMode === 'now' ? 'now-indicator--active' : ''}`} aria-hidden="true">
                  {form.journeyStartMode === 'now' ? '✓' : '○'}
                </span>
                Now
              </button>
              <input
                type="time"
                name="journeyTime"
                value={form.journeyTime}
                onChange={handleJourneyTimeChange}
              />
            </div>
          </section>

          <section className="card section-card">
            <h2>Route</h2>
            <div className="grid">
              <label>
                Start Postcode
                <input
                  name="start_postcode"
                  value={form.start_postcode}
                  onChange={handleChange}
                  required
                />
              </label>
              <label>
                Destination Postcode
                <input
                  name="end_postcode"
                  value={form.end_postcode}
                  onChange={handleChange}
                  required
                />
              </label>
            </div>
          </section>

          <section className="card section-card">
            <h2>Vehicle</h2>
            <div className="grid">
              <label>
                State of Charge (%)
                <input
                  name="soc"
                  type="number"
                  min="1"
                  max="100"
                  value={form.soc}
                  onChange={handleChange}
                  required
                />
              </label>
              <label>
                Car Model
                <select
                  name="car_model"
                  value={form.car_model}
                  onChange={handleChange}
                  disabled={loadingModels}
                >
                  <option value="">Select a model</option>
                  {models.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
                {modelsError && <span className="hint error">{modelsError}</span>}
              </label>
            </div>
          </section>

          <section className="card section-card">
            <h2>Mode</h2>
            <div className="mode-buttons">
              <button
                type="button"
                className={`mode-btn ${form.umbrella_choice === 'distance' ? 'mode-btn--active' : ''}`}
                onClick={() => handleModeSelect('distance')}
              >
                <span aria-hidden="true">🛣️</span>
                <span>Distance-Based</span>
              </button>
              <button
                type="button"
                className={`mode-btn ${form.umbrella_choice === 'meal' ? 'mode-btn--active' : ''}`}
                onClick={() => handleModeSelect('meal')}
              >
                <span aria-hidden="true">🍴</span>
                <span>Meal-Based</span>
              </button>
            </div>
          </section>

          <section className="card section-card">
            <h2>Additional Priorities</h2>
            <div className="priority-buttons">
              {PRIORITIES.map((p) => (
                <button
                  type="button"
                  key={p.key}
                  className={`filter-btn ${selectedPriorities.includes(p.key) ? 'filter-btn--active' : ''}`}
                  onClick={() => togglePriority(p.key)}
                  disabled={selectedPriorities.length >= 2 && !selectedPriorities.includes(p.key)}
                >
                  {p.label}
                </button>
              ))}
            </div>
            {selectedPriorities.length >= 2 && (
              <p className="hint priorities-hint">Only 2 priorities can be selected.</p>
            )}
          </section>

          <div className="actions">
            <button type="submit" disabled={loading || selectedPriorities.length !== 2}>
              {loading ? 'Loading…' : 'Get recommendations'}
            </button>
            <button type="button" onClick={loadProfileDefaults}>Load saved defaults</button>
            <button type="button" onClick={saveProfileDefaults}>Save as defaults</button>
            <button type="button" onClick={handleLogout}>Log out</button>
            {selectedPriorities.length !== 2 && (
              <span className="hint">Select exactly 2 priorities to match CLI.</span>
            )}
            {profileStatus && <span className="hint">{profileStatus}</span>}
          </div>
        </form>

        <section className="panel results">
          <div className="card summary-card">
            <h2>Stats</h2>
            {error && <p className="error">{error}</p>}
            {!error && !result && <p className="hint">Run a search to see recommendations.</p>}
            {result && (
              <>
                <div className="summary">
                  <div>
                    <span>Total Journey Distance</span>
                    <strong>{result.total_km?.toFixed?.(1) ?? result.total_km} km</strong>
                  </div>
                  <div>
                    <span>Estimated EV Range</span>
                    <strong>{result.est_range_km?.toFixed?.(1) ?? result.est_range_km} km</strong>
                  </div>
                </div>
              </>
            )}
          </div>

          {showMealFallbackNotice && (
            <div className="card">
              <p className="hint">Meal-Based options were unavailable for this time, so distance-based chargers are shown instead.</p>
            </div>
          )}

          {result && (
            <>
              {noChargingNeeded && (
                <div className="card">
                  <p className="hint">No charging stop is needed — your estimated EV range already covers this journey.</p>
                </div>
              )}
              <ul className="charger-list">
                {result.chargers?.map((c, i) => {
                if (noChargingNeeded) return null;
                const selectedDetails = getSelectedPriorityDetails(c);
                return (
                  <li key={c.id ?? i} className="card charger">
                    <div className="charger-top">
                      <div>
                        <span className="rank-badge">#{i + 1} {getRankLabel(i)}</span>
                        <h3>{c.title || 'Unknown charger'}</h3>
                      </div>
                    </div>

                    {i === 0 && <p className="top-reason">{getTopChargerReason(c)}</p>}

                    <div className="meta">
                      {hasValue(c.max_power) && !selectedPriorities.includes('max_power') && <span>Charging Power: {Math.round(c.max_power)} kW</span>}
                      {hasValue(c.is_fast) && <span>{c.is_fast ? 'Fast Charge' : 'Standard Charge'}</span>}
                      {hasValue(c.meal_stop) && <span>{c.meal_stop ? 'Meal Stop' : 'Distance Stop'}</span>}
                      {hasValue(c.route_km) && <span>Distance to Route: {formatRoundedKm(c.route_km)}</span>}
                    </div>

                    {selectedDetails.length > 0 && (
                      <div className="meta">
                        {selectedDetails.map((item) => (
                          <span key={item.key} className={isBestForPriority(c, item.key) ? 'meta-best' : ''}>{item.label}: {item.value}</span>
                        ))}
                      </div>
                    )}

                    {c.meal_stop && (
                      <details className="nearby-places">
                        <summary>{getNearbyStopsLabel(c)}</summary>
                        {Array.isArray(c.nearby_places) && c.nearby_places.length > 0 ? (
                          <ul>
                            {c.nearby_places.slice(0, 3).map((place, idx) => (
                              <li key={`${c.id ?? i}-nearby-${idx}`}>{place}</li>
                            ))}
                          </ul>
                        ) : (
                          <p className="hint">No restaurants/cafes found nearby for this stop.</p>
                        )}
                      </details>
                    )}
                  </li>
                );
                })}
              </ul>
            </>
          )}

        </section>
      </div>
    </main>
  );
}
