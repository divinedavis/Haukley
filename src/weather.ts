import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

// Local weather for the Haukley Weather channel. The channel itself is one national stream;
// the viewer's own forecast comes from haukley.com's weather API and is drawn by the app.
// TVs have no GPS: by default the server estimates the city from the request's address
// (nothing is sent but the request itself); a viewer can pick a city or type a ZIP instead.
export const API = 'https://haukley.com/api/weather/';
const KEY = 'haukley.weather.place.v1';

export type Place = { kind: 'auto' } | { kind: 'city'; slug: string; name: string } | { kind: 'zip'; zip: string };
export type Period = { name: string; temp: number; text: string; day: boolean };
export type LocalWeather = {
  place: { name: string; source: string; lat?: number; lon?: number };
  now: { temp: number; unit: string; text: string; wind?: string };
  periods: Period[];
  alerts: { event: string; headline?: string }[];
  updated?: string;
  attribution?: string;
};
export type City = { slug: string; name: string };
export type WeatherError = 'unknown_location' | 'unavailable' | 'offline';

export const AUTO: Place = { kind: 'auto' };

export const isZip = (z: string) => /^\d{5}$/.test(z.trim());

/** The /local URL for a place: no parameter at all for automatic (IP-based) location. */
export function localUrl(p: Place): string {
  if (p.kind === 'city') {
    return `${API}local?city=${encodeURIComponent(p.slug)}`;
  }
  if (p.kind === 'zip') {
    return `${API}local?zip=${encodeURIComponent(p.zip.trim())}`;
  }
  return `${API}local`;
}

export function placeLabel(p: Place): string {
  return p.kind === 'city' ? p.name : p.kind === 'zip' ? `ZIP ${p.zip}` : 'Your area (automatic)';
}

function valid(p: unknown): p is Place {
  const x = p as Place;
  if (!x || typeof x !== 'object') {
    return false;
  }
  if (x.kind === 'auto') {
    return true;
  }
  if (x.kind === 'city') {
    return typeof x.slug === 'string' && !!x.slug && typeof x.name === 'string';
  }
  return x.kind === 'zip' && typeof x.zip === 'string' && isZip(x.zip);
}

export async function loadPlace(): Promise<Place> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    const p = raw ? JSON.parse(raw) : null;
    return valid(p) ? p : AUTO;
  } catch {
    return AUTO;
  }
}

export async function savePlace(p: Place): Promise<void> {
  try {
    if (p.kind === 'auto') {
      await AsyncStorage.removeItem(KEY);
    } else {
      await AsyncStorage.setItem(KEY, JSON.stringify(p));
    }
  } catch {
    // Storage full or unavailable: the choice just won't survive a restart.
  }
}

type Result<T> = { ok: true; data: T } | { ok: false; error: WeatherError };

async function getJson<T>(url: string): Promise<Result<T>> {
  try {
    const r = await fetch(url, { headers: { Accept: 'application/json' } });
    if (r.status === 422) {
      return { ok: false, error: 'unknown_location' };
    }
    if (!r.ok) {
      return { ok: false, error: 'unavailable' };
    }
    return { ok: true, data: (await r.json()) as T };
  } catch {
    return { ok: false, error: 'offline' };
  }
}

export async function fetchLocal(p: Place): Promise<Result<LocalWeather>> {
  const r = await getJson<LocalWeather>(localUrl(p));
  if (r.ok && !(r.data && r.data.place && r.data.now && Array.isArray(r.data.periods))) {
    return { ok: false, error: 'unavailable' };
  }
  return r;
}

export async function fetchCities(): Promise<Result<City[]>> {
  const r = await getJson<{ cities: City[] }>(`${API}cities`);
  if (!r.ok) {
    return r;
  }
  const cities = (r.data?.cities ?? []).filter(c => c && c.slug && c.name);
  return { ok: true, data: cities };
}

export const errorText = (e: WeatherError) =>
  e === 'unknown_location'
    ? 'We couldn’t find that place. Pick a city or try another ZIP.'
    : e === 'offline'
    ? 'Can’t reach Haukley right now. Check the connection.'
    : 'Local weather isn’t available right now.';

/** The viewer's place (persisted) and its forecast, refetched when the place changes.
 *  enabled=false (any non-weather player) does nothing, so other titles make no request. */
export function useLocalWeather(enabled = true) {
  const [place, setPlaceState] = useState<Place | null>(null);
  const [weather, setWeather] = useState<LocalWeather | null>(null);
  const [error, setError] = useState<WeatherError | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!enabled) {
      return;
    }
    let alive = true;
    loadPlace().then(p => alive && setPlaceState(p));
    return () => {
      alive = false;
    };
  }, [enabled]);

  useEffect(() => {
    if (!place) {
      return;
    }
    let alive = true;
    setLoading(true);
    fetchLocal(place).then(r => {
      if (!alive) {
        return;
      }
      setLoading(false);
      if (r.ok) {
        setWeather(r.data);
        setError(null);
      } else {
        setWeather(null);
        setError(r.error);
      }
    });
    return () => {
      alive = false;
    };
  }, [place]);

  const setPlace = useCallback((p: Place) => {
    setPlaceState(p);
    savePlace(p);
  }, []);

  return { place, weather, error, loading, setPlace };
}
