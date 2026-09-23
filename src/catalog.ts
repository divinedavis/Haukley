import { TITLES } from './catalog.generated';
import type { Episode, Title } from './types';

export { TITLES };

const byId = new Map(TITLES.map(t => [t.id, t]));
export const getTitle = (id: string): Title => {
  const t = byId.get(id);
  if (!t) {
    throw new Error(`Unknown title ${id}`);
  }
  return t;
};
const pick = (ids: string[]) => ids.map(getTitle);

export const MOVIES = TITLES.filter(t => t.kind === 'movie');
export const SHOWS = TITLES.filter(t => t.kind === 'show');

// Public test streams (HLS) standing in for licensed content until DRM is wired up.
const STREAMS = [
  'https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8',
  'https://demo.unified-streaming.com/k8s/features/stable/video/tears-of-steel/tears-of-steel.ism/.m3u8',
  'https://devstreaming-cdn.apple.com/videos/streaming/examples/img_bipbop_adv_example_fmp4/master.m3u8',
];
export const streamFor = (id: string, episode = 0) => {
  let h = episode;
  for (const c of id) {
    h = (h * 31 + c.charCodeAt(0)) % 1000003;
  }
  return STREAMS[h % STREAMS.length];
};

export const FEATURED = pick(['glass-city', 'borough', 'night-line', 'signal', 'harbor-nine']);

export type UpNextItem = { title: Title; label: string; progress: number; episode?: number };
export const UP_NEXT: UpNextItem[] = [
  { title: getTitle('borough'), label: 'S3, E4 · 22 min left', progress: 0.58, episode: 4 },
  { title: getTitle('the-long-quiet'), label: '48 min left', progress: 0.62 },
  { title: getTitle('after-hours'), label: 'S4, E1 · Next Episode', progress: 0.02, episode: 1 },
  { title: getTitle('lighthouse-row'), label: 'S1, E6 · 9 min left', progress: 0.83, episode: 6 },
  { title: getTitle('headlights'), label: '1 hr 12 min left', progress: 0.31 },
];

export type Row =
  | { key: string; title: string; type: 'upNext'; items: UpNextItem[] }
  | { key: string; title: string; type: 'poster' | 'card' | 'ranked'; items: Title[] };

const homeRows: Row[] = [
  { key: 'up-next', title: 'Up Next', type: 'upNext', items: UP_NEXT },
  { key: 'top-movies', title: 'Top 10 Movies', type: 'ranked', items: pick(['night-line', 'glass-city', 'iron-meridian', 'harbor-nine', 'ghost-light', 'headlights', 'saltwater-hymn', 'last-train-to-halden', 'paper-kites', 'sparks']) },
  { key: 'new-shows', title: 'New & Noteworthy Shows', type: 'card', items: pick(['signal', 'commonwealth', 'chrome', 'high-altitude', 'lighthouse-row', 'tidewater']) },
  { key: 'top-shows', title: 'Top 10 TV Shows', type: 'ranked', items: pick(['borough', 'signal', 'after-hours', 'tidewater', 'wildwood', 'commonwealth', 'lighthouse-row', 'slow-roads', 'chrome', 'high-altitude']) },
  { key: 'because', title: 'Because You Watched Night Line', type: 'card', items: pick(['headlights', 'last-train-to-halden', 'saltwater-hymn', 'iron-meridian', 'tidewater', 'ghost-light']) },
  { key: 'new-movies', title: 'New Releases', type: 'poster', items: pick(['glass-city', 'ghost-light', 'headlights', 'harbor-nine', 'saltwater-hymn', 'iron-meridian', 'night-line']) },
  { key: 'escape', title: 'Get Away From It All', type: 'card', items: pick(['salt-and-sand', 'northbound', 'slow-roads', 'high-altitude', 'wildwood', 'the-cartographer']) },
  { key: 'feel-good', title: 'Feel-Good Favorites', type: 'poster', items: pick(['paper-kites', 'sparks', 'after-hours', 'chrome', 'salt-and-sand', 'slow-roads', 'wildwood']) },
];

export const ROWS: Record<'home' | 'movies' | 'shows', Row[]> = {
  home: homeRows,
  movies: [
    { key: 'm-all', title: 'All Movies', type: 'poster', items: MOVIES },
    { key: 'm-thrill', title: 'Edge of Your Seat', type: 'card', items: MOVIES.filter(t => /Thriller|Crime|Heist|Action|Horror|Mystery/.test(t.genre)) },
    { key: 'm-heart', title: 'Stories With Heart', type: 'card', items: MOVIES.filter(t => /Drama|Romance|Comedy|Adventure/.test(t.genre)) },
  ],
  shows: [
    { key: 's-all', title: 'All Shows', type: 'poster', items: SHOWS },
    { key: 's-binge', title: 'Binge-Worthy Dramas', type: 'card', items: SHOWS.filter(t => /Drama|Thriller|Mystery|Sci-Fi/.test(t.genre)) },
    { key: 's-light', title: 'Light & Easy', type: 'card', items: SHOWS.filter(t => /Comedy|Travel|Docuseries/.test(t.genre)) },
  ],
};

const EPISODE_NAMES = ['Pilot', 'The Long Way Home', 'Undercurrent', 'Second Chances', 'Low Tide', 'What We Keep', 'Crossing Lines', 'The Reckoning'];
export const episodesFor = (t: Title): Episode[] =>
  EPISODE_NAMES.map((name, i) => ({
    number: i + 1,
    name,
    minutes: 42 + ((i * 7 + t.id.length) % 14),
    summary: i === 0 ? t.description : `The fallout from last week's discovery forces everyone in ${t.title} to choose a side.`,
  }));

export const moreLike = (t: Title) =>
  TITLES.filter(x => x.id !== t.id && x.kind === t.kind).slice(0, 8);
