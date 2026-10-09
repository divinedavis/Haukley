import AsyncStorage from '@react-native-async-storage/async-storage';
import catalog from '../scripts/catalog.json';
import rows from '../scripts/rows.json';
import { TITLES as BUNDLED } from './catalog.generated';
import type { Episode, Title } from './types';

// The catalog every platform shares is haukley.com/watch/catalog/catalog.json (built by
// scripts/make_web.py). The app ships a bundled copy; loadCatalog() swaps in the copy fetched
// on a previous launch and refreshCatalog() fetches the next one, so new films reach TVs
// without an app update. Art comes from the bundle when present, otherwise from haukley.com.
const BASE = 'https://haukley.com/watch/catalog/';
const CACHE_KEY = 'haukley.catalog.v1';

type RemoteEpisode = Episode & { stream: string };
type RemoteTitle = Omit<Title, 'poster' | 'card' | 'backdrop' | 'stills' | 'episodes'> & {
  stream: string;
  episodes: RemoteEpisode[];
};
type RemoteRow = { key: string; title: string; type: string; ids: string[] };
type RemoteCatalog = { titles: RemoteTitle[]; featured: string[]; rows: RemoteRow[] };

export type UpNextItem = { title: Title; label: string; progress: number; episode?: number };
export type Row =
  | { key: string; title: string; type: 'upNext'; items: UpNextItem[] }
  | { key: string; title: string; type: 'poster' | 'card' | 'ranked'; items: Title[] };

export let TITLES: Title[] = [];
export let MOVIES: Title[] = [];
export let SHOWS: Title[] = [];
export let FEATURED: Title[] = [];
export let UP_NEXT: UpNextItem[] = [];
export let ROWS: Record<'home' | 'movies' | 'shows', Row[]> = { home: [], movies: [], shows: [] };
let byId = new Map<string, Title>();
let streams = new Map<string, string>();

export const getTitle = (id: string): Title => {
  const t = byId.get(id);
  if (!t) {
    throw new Error(`Unknown title ${id}`);
  }
  return t;
};
export const hasTitle = (id: string) => byId.has(id);
// Rows can name titles this build doesn't have: skip them.
const pick = (ids: string[]) => ids.flatMap(id => (byId.has(id) ? [getTitle(id)] : []));

function apply(titles: Title[], featured: string[], homeRows: RemoteRow[], streamById: Map<string, string>) {
  TITLES = titles;
  byId = new Map(titles.map(t => [t.id, t]));
  streams = streamById;
  // Live channels appear only in the rows that name them (the Live TV row).
  MOVIES = titles.filter(t => t.kind === 'movie');
  SHOWS = titles.filter(t => t.kind === 'show');
  FEATURED = pick(featured);
  type UpNextSeed = { id: string; label: string; progress: number; episode?: number };
  UP_NEXT = (rows.upNext as UpNextSeed[]).flatMap(u => (byId.has(u.id) ? [{ ...u, title: getTitle(u.id) }] : []));
  const nonEmpty = (list: Row[]) => list.filter(r => r.items.length > 0);
  ROWS = {
    home: [
      { key: 'up-next', title: 'Up Next', type: 'upNext', items: UP_NEXT },
      ...nonEmpty(homeRows.map(r => ({ key: r.key, title: r.title, type: r.type as 'poster' | 'card' | 'ranked', items: pick(r.ids) }))),
    ],
    movies: nonEmpty([
      { key: 'm-all', title: 'All Movies', type: 'poster', items: MOVIES },
      { key: 'm-comedy', title: 'Comedy', type: 'card', items: MOVIES.filter(t => /Comedy/.test(t.genre)) },
      { key: 'm-thrill', title: 'Horror & Thrillers', type: 'card', items: MOVIES.filter(t => /Thriller|Crime|Action|Horror|Mystery|Noir/.test(t.genre)) },
      { key: 'm-scifi', title: 'Sci-Fi, Fantasy & Animation', type: 'card', items: MOVIES.filter(t => /Sci-Fi|Fantasy|Animation|Adventure/.test(t.genre)) },
      { key: 'm-drama', title: 'Drama, War & Documentary', type: 'card', items: MOVIES.filter(t => /Drama|War|Documentary|Romance|Western/.test(t.genre)) },
    ]),
    shows: nonEmpty([
      { key: 's-all', title: 'All Shows', type: 'poster', items: SHOWS },
      { key: 's-docs', title: 'Documentary Series', type: 'card', items: SHOWS.filter(t => /Documentary|Docuseries|History/.test(t.genre)) },
      { key: 's-classic', title: 'Classic TV', type: 'card', items: SHOWS.filter(t => !/Documentary|Docuseries|History/.test(t.genre)) },
    ]),
  };
}

function fromBundle() {
  const s = new Map<string, string>();
  const live = (catalog as { live?: { id: string; stream?: string }[] }).live ?? [];
  for (const t of [...catalog.movies, ...catalog.shows, ...live] as { id: string; stream?: string }[]) {
    if (t.stream) {
      s.set(t.id, t.stream);
    }
  }
  apply(BUNDLED, rows.featured, rows.home, s);
}

const art = (id: string, name: string) => ({ uri: `${BASE}${encodeURIComponent(id)}/${name}.jpg` });

function fromRemote(remote: RemoteCatalog) {
  const bundled = new Map(BUNDLED.map(t => [t.id, t]));
  const s = new Map<string, string>();
  const titles = remote.titles.map((r): Title => {
    s.set(r.id, r.stream);
    const b = bundled.get(r.id);
    const kind = r.kind === 'show' || r.kind === 'live' ? r.kind : 'movie';
    return {
      kind, id: r.id, title: r.title, genre: r.genre, year: r.year, rating: r.rating, tagline: r.tagline,
      description: r.description, credits: r.credits, license: r.license ?? undefined,
      advisory: r.advisory ?? undefined,
      runtime: r.runtime, seasons: r.seasons ?? undefined,
      poster: b?.poster ?? art(r.id, 'poster'),
      card: b?.card ?? art(r.id, 'card'),
      backdrop: b?.backdrop ?? art(r.id, 'backdrop'),
      stills: kind === 'show' ? r.episodes.map(e => art(r.id, `ep${e.number}`)) : undefined,
      episodes: r.episodes?.length ? r.episodes : undefined,
    };
  });
  apply(titles, remote.featured, remote.rows, s);
}

fromBundle();

const valid = (c: unknown): c is RemoteCatalog =>
  !!c && Array.isArray((c as RemoteCatalog).titles) && (c as RemoteCatalog).titles.length > 0 && Array.isArray((c as RemoteCatalog).rows);

/** Swap in the catalog saved by the last refresh (call before first render). */
export async function loadCatalog() {
  try {
    const raw = await AsyncStorage.getItem(CACHE_KEY);
    const c = raw ? JSON.parse(raw) : null;
    if (valid(c)) {
      fromRemote(c);
    }
  } catch {
    // Keep the bundled catalog.
  }
}

/** Fetch the live catalog for next launch (never changes what's on screen now). */
export async function refreshCatalog() {
  try {
    const r = await fetch(`${BASE}catalog.json`, { headers: { 'Cache-Control': 'no-cache' } });
    if (r.ok) {
      const c = await r.json();
      if (valid(c)) {
        await AsyncStorage.setItem(CACHE_KEY, JSON.stringify(c));
      }
    }
  } catch {
    // Offline: try again next launch.
  }
}

// Placeholder test streams for titles without their own (none in the real catalog).
const STREAMS = rows.streams;
export const streamFor = (id: string, episode = 0) => {
  const t = byId.get(id);
  const ep = episode ? t?.episodes?.find(e => e.number === episode) : undefined;
  if (ep) {
    return ep.stream;
  }
  const own = streams.get(id);
  if (own) {
    return own;
  }
  let h = episode;
  for (const c of id) {
    h = (h * 31 + c.charCodeAt(0)) % 1000003;
  }
  return STREAMS[h % STREAMS.length];
};

const EPISODE_NAMES = rows.episodeNames;
export const episodesFor = (t: Title): Episode[] =>
  t.episodes ??
  EPISODE_NAMES.map((name, i) => ({
    number: i + 1,
    name,
    minutes: 42 + ((i * 7 + t.id.length) % 14),
    summary: i === 0 ? t.description : `The fallout from last week's discovery forces everyone in ${t.title} to choose a side.`,
  }));

export const moreLike = (t: Title) =>
  t.kind === 'live' ? [] : TITLES.filter(x => x.id !== t.id && x.kind === t.kind).slice(0, 8);
export const isLive = (id: string) => byId.get(id)?.kind === 'live';
