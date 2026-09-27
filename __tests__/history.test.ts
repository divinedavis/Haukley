import AsyncStorage from '@react-native-async-storage/async-storage';
import rows from '../scripts/rows.json';
import { __resetHistoryForTests, clock, loadHistory, recordWatch, resumeAt, timeLeftLabel } from '../src/history';

beforeEach(async () => {
  await AsyncStorage.clear();
  __resetHistoryForTests();
});

test('first run seeds Up Next from rows.json (empty for the real catalog)', async () => {
  const seeded = await loadHistory();
  expect(seeded).toHaveLength(rows.upNext.length);
});

test('mid-film position is saved and resumable', async () => {
  await recordWatch('glass-city', 0, 754, 3600);
  expect(resumeAt('glass-city')).toBe(754);
  const saved = JSON.parse((await AsyncStorage.getItem('haukley.watch.v1')) as string);
  expect(saved[0]).toMatchObject({ id: 'glass-city', episode: 0, position: 754 });
});

test('episodes are tracked separately', async () => {
  await recordWatch('signal', 2, 600, 2700);
  expect(resumeAt('signal', 2)).toBe(600);
  expect(resumeAt('signal', 3)).toBe(0);
});

test('barely started or finished titles drop out', async () => {
  await recordWatch('glass-city', 0, 754, 3600);
  await recordWatch('glass-city', 0, 3500, 3600);
  expect(resumeAt('glass-city')).toBe(0);
  await recordWatch('sparks', 0, 4, 3600);
  expect(resumeAt('sparks')).toBe(0);
});

test('labels', () => {
  expect(clock(754)).toBe('12:34');
  expect(clock(3725)).toBe('1:02:05');
  expect(timeLeftLabel({ id: 'x', episode: 0, position: 600, duration: 4920, updatedAt: 0 })).toBe('1 hr 12 min left');
  expect(timeLeftLabel({ id: 'x', episode: 4, position: 1200, duration: 2520, updatedAt: 0 })).toBe('E4 · 22 min left');
});
