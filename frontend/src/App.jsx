import { useEffect, useMemo, useState } from 'react';
import {
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signOut,
} from 'firebase/auth';
import { auth, authInitError } from './firebase';
import { fetchCarModels } from './services/apiClient';
import {
  PRIORITIES,
  PRIORITY_DIRECTIONS,
  PRIORITY_VALUE_FORMATTERS,
  hasValue,
  toNumber,
  getPriorityScore,
} from './features/routing/mappers';
import { useAuth } from './hooks/useAuth';
import {
  loadProfileDefaults as loadProfileDefaultsApi,
  persistProfileDefaults as persistProfileDefaultsApi,
  toProfileDraft,
} from './hooks/useProfileDefaults';
import { submitRouteRequest } from './hooks/useRoutePlanner';
import {
  getNearbyStopsLabel,
  formatRoundedKm,
  getRankLabel,
} from './features/routing/RoutingResultHelpers';

export default function App() {
  const { authReady, currentUser } = useAuth(auth);
  const [authMode, setAuthMode] = useState('login');
  const [authForm, setAuthForm] = useState({ email: '', password: '' });
  const [authError, setAuthError] = useState(null);
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const [savedDefaults, setSavedDefaults] = useState(null);
  const [loadingSavedDefaults, setLoadingSavedDefaults] = useState(false);
  const [profileDefaultsOpen, setProfileDefaultsOpen] = useState(false);
  const [profileDraft, setProfileDraft] = useState({
    car_model: '',
    home_destination_postcode: '',
    default_mode: 'distance',
    default_priorities: [],
  });

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
    if (!currentUser) {
      setModels([]);
      setLoadingModels(false);
      setSavedDefaults(null);
      setProfileDefaultsOpen(false);
      setProfileDraft({
        car_model: '',
        home_destination_postcode: '',
        default_mode: 'distance',
        default_priorities: [],
      });
      return undefined;
    }

    let cancelled = false;
    setLoadingModels(true);
    currentUser.getIdToken()
      .then((token) => fetchCarModels(token))
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

  const fetchSavedDefaults = async () => {
    const profile = await loadProfileDefaultsApi(currentUser);
    if (!profile) return null;
    setSavedDefaults(profile);
    setProfileDraft(toProfileDraft(profile));
    return profile;
  };

  useEffect(() => {
    if (!currentUser) return;
    let cancelled = false;
    setLoadingSavedDefaults(true);
    fetchSavedDefaults()
      .catch((err) => {
        if (!cancelled) setProfileStatus(err.message || 'Failed to load profile defaults');
      })
      .finally(() => {
        if (!cancelled) setLoadingSavedDefaults(false);
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

  const handleProfileDraftChange = (e) => {
    const { name, value } = e.target;
    setProfileDraft((prev) => ({ ...prev, [name]: value }));
  };

  const toggleProfileDraftPriority = (key) => {
    setProfileDraft((prev) => {
      if (prev.default_priorities.includes(key)) {
        return {
          ...prev,
          default_priorities: prev.default_priorities.filter((p) => p !== key),
        };
      }
      if (prev.default_priorities.length >= 2) return prev;
      return {
        ...prev,
        default_priorities: [...prev.default_priorities, key],
      };
    });
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
      setProfileMenuOpen(false);
    } catch (err) {
      setAuthError(getFriendlyAuthError(err));
    }
  };

  const handleLogout = async () => {
    await signOut(auth);
    setResult(null);
    setSelectedPriorities([]);
    setProfileStatus(null);
    setSavedDefaults(null);
    setProfileDefaultsOpen(false);
    setProfileMenuOpen(false);
    setError(null);
  };

  const persistProfileDefaults = async (payload) => {
    const updatedProfile = await persistProfileDefaultsApi(currentUser, payload);
    setSavedDefaults(updatedProfile);
    return updatedProfile;
  };

  const saveProfileDefaults = async () => {
    if (!currentUser) {
      setProfileStatus('Sign in to save defaults.');
      return;
    }
    try {
      setProfileStatus('Saving defaults...');
      const payload = {
        car_model: form.car_model || null,
        home_destination_postcode: form.end_postcode.trim() || null,
        default_mode: form.umbrella_choice || 'distance',
        default_priorities: selectedPriorities,
      };
      const updatedProfile = await persistProfileDefaults(payload);
      setProfileDraft(toProfileDraft(updatedProfile));
      setProfileStatus('Defaults saved.');
    } catch (err) {
      setProfileStatus(err.message || 'Failed to save defaults');
    }
  };

  const saveProfileDefaultsFromMenu = async () => {
    if (!currentUser) {
      setProfileStatus('Sign in to save defaults.');
      return;
    }
    try {
      setProfileStatus('Saving defaults...');
      const payload = {
        car_model: profileDraft.car_model || null,
        home_destination_postcode: profileDraft.home_destination_postcode.trim() || null,
        default_mode: profileDraft.default_mode || 'distance',
        default_priorities: profileDraft.default_priorities,
      };
      const updatedProfile = await persistProfileDefaults(payload);
      setProfileDraft(toProfileDraft(updatedProfile));
      setProfileStatus('Defaults saved.');
    } catch (err) {
      setProfileStatus(err.message || 'Failed to save defaults');
    }
  };

  const toggleSavedDefaultsPanel = async () => {
    const nextOpen = !profileDefaultsOpen;
    setProfileDefaultsOpen(nextOpen);
    if (!nextOpen) return;
    if (savedDefaults) {
      setProfileDraft(toProfileDraft(savedDefaults));
      return;
    }
    try {
      setLoadingSavedDefaults(true);
      await fetchSavedDefaults();
    } catch (err) {
      setProfileStatus(err.message || 'Failed to load profile defaults');
    } finally {
      setLoadingSavedDefaults(false);
    }
  };

  const loadProfileDefaults = async () => {
    if (!currentUser) {
      setProfileStatus('Sign in to load defaults.');
      return;
    }
    try {
      setProfileStatus('Loading defaults...');
      const profile = await fetchSavedDefaults();

      setForm((prev) => ({
        ...prev,
        car_model: profile.car_model ?? '',
        end_postcode: profile.home_destination_postcode ?? '',
        umbrella_choice: profile.default_mode ?? 'distance',
      }));
      setSelectedPriorities(profile.default_priorities || []);
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
      const validScores = scores.filter((score) => !Number.isNaN(score));
      if (validScores.length === 0) continue;
      out[key] = direction === 'min' ? Math.min(...validScores) : Math.max(...validScores);
    }
    return out;
  }, [result, selectedPriorities]);

  const isBestForPriority = (charger, key) => {
    const bestScore = bestPriorityScores[key];
    if (typeof bestScore !== 'number' || Number.isNaN(bestScore)) return false;
    const score = getPriorityScore(charger, key);
    if (Number.isNaN(score)) return false;
    return Math.abs(score - bestScore) < 1e-9;
  };

  const noChargingNeeded = result && toNumber(result.est_range_km) >= toNumber(result.total_km);
  const rankedChargers = useMemo(() => {
    const chargers = Array.isArray(result?.chargers) ? [...result.chargers] : [];
    if (chargers.length <= 1 || selectedPriorities.length === 0) return chargers;

    const compareByPriority = (a, b, key) => {
      const direction = PRIORITY_DIRECTIONS[key] || 'max';
      const aScore = getPriorityScore(a, key);
      const bScore = getPriorityScore(b, key);
      const aMissing = Number.isNaN(aScore);
      const bMissing = Number.isNaN(bScore);

      if (aMissing && bMissing) return 0;
      if (aMissing) return 1;
      if (bMissing) return -1;

      if (Math.abs(aScore - bScore) < 1e-9) return 0;
      if (direction === 'min') return aScore < bScore ? -1 : 1;
      return aScore > bScore ? -1 : 1;
    };

    return chargers.sort((a, b) => {
      for (const key of selectedPriorities) {
        const cmp = compareByPriority(a, b, key);
        if (cmp !== 0) return cmp;
      }
      return 0;
    });
  }, [result, selectedPriorities]);

  const showMealFallbackNotice = (
    form.umbrella_choice === 'meal'
    && !!result
    && !noChargingNeeded
    && rankedChargers.length > 0
    && !rankedChargers.some((charger) => charger?.meal_stop)
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
      const data = await submitRouteRequest(currentUser, payload);
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

  return (
    <main className="page">
      <header className="header">
        <h1>EV Charger Planner</h1>
        <div className="profile-menu-wrap">
          <button type="button" className="profile-btn" onClick={() => setProfileMenuOpen((prev) => !prev)}>
            {currentUser ? 'Profile' : 'Sign in'}
          </button>
          {profileMenuOpen && (
            <div className="profile-menu card">
              {currentUser ? (
                <>
                  <p className="hint">Signed in as {currentUser.email}</p>
                  <button type="button" onClick={toggleSavedDefaultsPanel}>
                    Defaults
                  </button>
                  {profileDefaultsOpen && (
                    <div className="profile-submenu">
                      <div className="profile-mini-form">
                        {loadingSavedDefaults && <p className="hint">Refreshing saved defaults...</p>}
                        <label>
                          Car model
                          <select
                            name="car_model"
                            value={profileDraft.car_model}
                            onChange={handleProfileDraftChange}
                            disabled={loadingModels}
                          >
                            <option value="">Select a model</option>
                            {models.map((modelName) => (
                              <option key={modelName} value={modelName}>{modelName}</option>
                            ))}
                          </select>
                        </label>

                        <label>
                          Home destination postcode
                          <input
                            name="home_destination_postcode"
                            value={profileDraft.home_destination_postcode}
                            onChange={handleProfileDraftChange}
                            placeholder="e.g. SW6 4BL"
                          />
                        </label>

                        <label>
                          Default mode
                          <select
                            name="default_mode"
                            value={profileDraft.default_mode}
                            onChange={handleProfileDraftChange}
                          >
                            <option value="distance">Distance-Based</option>
                            <option value="meal">Meal-Based</option>
                          </select>
                        </label>

                        <p className="hint">Default priorities (choose up to 2)</p>
                        <div className="profile-priority-row">
                          {PRIORITIES.map((priority) => (
                            <button
                              type="button"
                              key={`profile-${priority.key}`}
                              className={`filter-btn ${profileDraft.default_priorities.includes(priority.key) ? 'filter-btn--active' : ''}`}
                              onClick={() => toggleProfileDraftPriority(priority.key)}
                              disabled={profileDraft.default_priorities.length >= 2 && !profileDraft.default_priorities.includes(priority.key)}
                            >
                              {priority.label}
                              {profileDraft.default_priorities.includes(priority.key) && (
                                <span className="priority-order-badge">{profileDraft.default_priorities.indexOf(priority.key) + 1}</span>
                              )}
                            </button>
                          ))}
                        </div>
                        <p className="hint">Selection order sets weighting: 1 is stronger than 2.</p>

                        <div className="actions">
                          <button type="button" onClick={saveProfileDefaultsFromMenu}>Save defaults</button>
                          <button type="button" onClick={loadProfileDefaults}>Load into planner</button>
                        </div>
                      </div>
                    </div>
                  )}
                  <button type="button" onClick={handleLogout}>Sign out</button>
                </>
              ) : (
                <>
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
                  </form>
                </>
              )}
            </div>
          )}
        </div>
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
                  {selectedPriorities.includes(p.key) && (
                    <span className="priority-order-badge">{selectedPriorities.indexOf(p.key) + 1}</span>
                  )}
                </button>
              ))}
            </div>
            <p className="hint priorities-hint">Selection order sets weighting: 1 is stronger than 2.</p>
            {selectedPriorities.length >= 2 && (
              <p className="hint priorities-hint">Only 2 priorities can be selected.</p>
            )}
          </section>

          <div className="actions">
            <button type="submit" disabled={loading || selectedPriorities.length !== 2}>
              {loading ? 'Loading…' : 'Get recommendations'}
            </button>
            <button type="button" onClick={loadProfileDefaults} disabled={!currentUser}>Load saved defaults</button>
            <button type="button" onClick={saveProfileDefaults} disabled={!currentUser}>Save as defaults</button>
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
                {rankedChargers?.map((c, i) => {
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
