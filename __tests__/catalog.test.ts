import AsyncStorage from '@react-native-async-storage/async-storage';
import { MOVIES, ROWS, SHOWS, getTitle, isLive, loadCatalog, moreLike, streamFor } from '../src/catalog';

// The live catalog replaces the bundled one from the second launch on; every field the
// title page shows has to survive that swap (the rights line once didn't).
test('a saved live catalog keeps each title\'s rights line', async () => {
  const remote = {
    titles: [{
      id: 'sintel', kind: 'movie', title: 'Sintel', genre: 'Animation', year: 2010, rating: 'NR',
      tagline: 't', description: 'd', credits: 'Directed by Colin Levy', runtime: '15 min',
      stream: 'https://example.com/sintel.m3u8', episodes: [],
      license: '© copyright Blender Foundation · https://creativecommons.org/licenses/by/3.0/',
    }],
    featured: ['sintel'],
    rows: [{ key: 'r', title: 'Row', type: 'card', ids: ['sintel'] }],
  };
  await AsyncStorage.setItem('haukley.catalog.v1', JSON.stringify(remote));
  await loadCatalog();
  expect(getTitle('sintel').license).toContain('creativecommons.org/licenses/by/3.0');
});

// Live channels (kind 'live', e.g. Haukley Weather) stay live through the remote swap and
// only appear in the rows that name them.
test('a live channel keeps kind live and stays out of Movies, Shows and More Like This', async () => {
  const movie = {
    id: 'sintel', kind: 'movie', title: 'Sintel', genre: 'Animation', year: 2010, rating: 'NR',
    tagline: 't', description: 'd', credits: 'c', runtime: '15 min', license: 'CC BY',
    stream: 'https://example.com/sintel.m3u8', episodes: [],
  };
  const live = {
    id: 'haukley-weather', kind: 'live', title: 'Haukley Weather', genre: 'Weather', year: 2026,
    rating: 'TV-G', tagline: 't', description: 'd', credits: 'Data: NOAA', runtime: null,
    license: 'NOAA public domain', stream: 'https://haukley.com/live/weather/index.m3u8', episodes: [],
  };
  const remote = {
    titles: [movie, live],
    featured: ['sintel'],
    rows: [{ key: 'live', title: 'Live TV', type: 'card', ids: ['haukley-weather'] }],
  };
  await AsyncStorage.setItem('haukley.catalog.v1', JSON.stringify(remote));
  await loadCatalog();
  expect(getTitle('haukley-weather').kind).toBe('live');
  expect(isLive('haukley-weather')).toBe(true);
  expect(streamFor('haukley-weather')).toBe('https://haukley.com/live/weather/index.m3u8');
  expect(MOVIES.map(t => t.id)).toEqual(['sintel']);
  expect(SHOWS).toHaveLength(0);
  expect(moreLike(getTitle('haukley-weather'))).toEqual([]);
  expect(moreLike(getTitle('sintel')).map(t => t.id)).not.toContain('haukley-weather');
  const home = ROWS.home.find(r => r.key === 'live');
  expect(home && home.type !== 'upNext' && home.items.map(t => t.id)).toEqual(['haukley-weather']);
});

test('the bundled catalog has the weather channel as kind live with its stream', () => {
  jest.isolateModules(() => {
    const c = require('../src/catalog');
    expect(c.getTitle('haukley-weather').kind).toBe('live');
    expect(c.streamFor('haukley-weather')).toMatch(/^https:\/\/haukley\.com\/live\//);
    expect(c.ROWS.home[1].key).toBe('live');
  });
});
