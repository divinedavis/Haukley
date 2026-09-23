import rows from '../scripts/rows.json';
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
// Same hash as scripts/make_roku.py so every platform plays the same stream per title.
const STREAMS = rows.streams;
export const streamFor = (id: string, episode = 0) => {
  let h = episode;
  for (const c of id) {
    h = (h * 31 + c.charCodeAt(0)) % 1000003;
  }
  return STREAMS[h % STREAMS.length];
};

export const FEATURED = pick(rows.featured);

export type UpNextItem = { title: Title; label: string; progress: number; episode?: number };
export const UP_NEXT: UpNextItem[] = rows.upNext.map(u => ({ ...u, title: getTitle(u.id) }));

export type Row =
  | { key: string; title: string; type: 'upNext'; items: UpNextItem[] }
  | { key: string; title: string; type: 'poster' | 'card' | 'ranked'; items: Title[] };

const homeRows: Row[] = [
  { key: 'up-next', title: 'Up Next', type: 'upNext', items: UP_NEXT },
  ...rows.home.map(r => ({ key: r.key, title: r.title, type: r.type as 'poster' | 'card' | 'ranked', items: pick(r.ids) })),
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

const EPISODE_NAMES = rows.episodeNames;
export const episodesFor = (t: Title): Episode[] =>
  EPISODE_NAMES.map((name, i) => ({
    number: i + 1,
    name,
    minutes: 42 + ((i * 7 + t.id.length) % 14),
    summary: i === 0 ? t.description : `The fallout from last week's discovery forces everyone in ${t.title} to choose a side.`,
  }));

export const moreLike = (t: Title) =>
  TITLES.filter(x => x.id !== t.id && x.kind === t.kind).slice(0, 8);
