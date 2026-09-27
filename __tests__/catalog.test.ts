import AsyncStorage from '@react-native-async-storage/async-storage';
import { getTitle, loadCatalog } from '../src/catalog';

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
