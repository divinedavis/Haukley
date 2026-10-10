import AsyncStorage from '@react-native-async-storage/async-storage';
import { AUTO, API, errorText, fetchCities, fetchLocal, isZip, loadPlace, localUrl, placeLabel, savePlace } from '../src/weather';

const okWeather = {
  place: { name: 'Brooklyn, NY', source: 'ip', lat: 40.68, lon: -73.94 },
  now: { temp: 63.4, unit: 'F', text: 'Partly Cloudy', wind: 'W 8 mph' },
  periods: [{ name: 'Tonight', temp: 55, text: 'Clear', day: false }],
  alerts: [],
  updated: '2026-10-10T20:00:00Z',
  attribution: 'NOAA / National Weather Service',
};

function mockFetch(status: number, body: unknown) {
  const fn = jest.fn().mockResolvedValue({ ok: status >= 200 && status < 300, status, json: async () => body });
  (globalThis as unknown as { fetch: unknown }).fetch = fn;
  return fn;
}

beforeEach(async () => {
  await AsyncStorage.clear();
});

test('local URL: automatic sends no location, city and ZIP send only that', () => {
  expect(localUrl(AUTO)).toBe(`${API}local`);
  expect(localUrl({ kind: 'city', slug: 'new-york', name: 'New York' })).toBe(`${API}local?city=new-york`);
  expect(localUrl({ kind: 'zip', zip: ' 11201 ' })).toBe(`${API}local?zip=11201`);
  expect(localUrl({ kind: 'city', slug: 'a b&c', name: 'x' })).toBe(`${API}local?city=a%20b%26c`);
});

test('ZIP validation and labels', () => {
  expect(isZip('11201')).toBe(true);
  expect(isZip('1120')).toBe(false);
  expect(isZip('11201-1234')).toBe(false);
  expect(placeLabel(AUTO)).toMatch(/automatic/);
  expect(placeLabel({ kind: 'zip', zip: '11201' })).toBe('ZIP 11201');
});

test('the chosen place persists; automatic clears it; junk falls back to automatic', async () => {
  expect(await loadPlace()).toEqual(AUTO);
  await savePlace({ kind: 'city', slug: 'chicago', name: 'Chicago' });
  expect(await loadPlace()).toEqual({ kind: 'city', slug: 'chicago', name: 'Chicago' });
  await savePlace(AUTO);
  expect(await AsyncStorage.getItem('haukley.weather.place.v1')).toBeNull();
  await AsyncStorage.setItem('haukley.weather.place.v1', JSON.stringify({ kind: 'zip', zip: 'abc' }));
  expect(await loadPlace()).toEqual(AUTO);
  await AsyncStorage.setItem('haukley.weather.place.v1', '{not json');
  expect(await loadPlace()).toEqual(AUTO);
});

test('fetchLocal: success, unknown location (422), server down (503), bad body, offline', async () => {
  const f = mockFetch(200, okWeather);
  expect(await fetchLocal({ kind: 'zip', zip: '11201' })).toEqual({ ok: true, data: okWeather });
  expect(f).toHaveBeenCalledWith(`${API}local?zip=11201`, expect.anything());

  mockFetch(422, { error: 'unknown_location' });
  expect(await fetchLocal({ kind: 'zip', zip: '00000' })).toEqual({ ok: false, error: 'unknown_location' });

  mockFetch(503, { error: 'unavailable' });
  expect(await fetchLocal(AUTO)).toEqual({ ok: false, error: 'unavailable' });

  mockFetch(200, { hello: 'world' });
  expect(await fetchLocal(AUTO)).toEqual({ ok: false, error: 'unavailable' });

  (globalThis as unknown as { fetch: unknown }).fetch = jest.fn().mockRejectedValue(new Error('network'));
  expect(await fetchLocal(AUTO)).toEqual({ ok: false, error: 'offline' });
});

test('fetchCities drops malformed rows and reports errors', async () => {
  mockFetch(200, { cities: [{ slug: 'new-york', name: 'New York' }, { slug: '', name: 'x' }, null] });
  expect(await fetchCities()).toEqual({ ok: true, data: [{ slug: 'new-york', name: 'New York' }] });
  mockFetch(500, {});
  expect(await fetchCities()).toEqual({ ok: false, error: 'unavailable' });
});

test('every error has viewer-facing text', () => {
  for (const e of ['unknown_location', 'unavailable', 'offline'] as const) {
    expect(errorText(e).length).toBeGreaterThan(10);
  }
});
