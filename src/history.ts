import AsyncStorage from '@react-native-async-storage/async-storage';
import { useEffect, useState } from 'react';
import rows from '../scripts/rows.json';

/** Where a viewer stopped in a movie (episode 0) or an episode, kept on the device. */
export type Watch = { id: string; episode: number; position: number; duration: number; updatedAt: number };

const KEY = 'haukley.watch.v1';
const MAX = 30;

let cache: Watch[] | null = null;
const listeners = new Set<(w: Watch[]) => void>();

// First run: seed from rows.json's Up Next so the row reads the way it will in use
// (same as the iPhone app). Real viewing replaces these as it happens.
function seed(): Watch[] {
  const now = Date.now();
  return (rows.upNext as { id: string; episode?: number; progress: number }[]).map((u, i) => {
    const duration = 45 * 60;
    return { id: u.id, episode: u.episode ?? 0, position: Math.round(u.progress * duration), duration, updatedAt: now - i * 3600_000 };
  });
}

export async function loadHistory(): Promise<Watch[]> {
  if (cache) {
    return cache;
  }
  try {
    const raw = await AsyncStorage.getItem(KEY);
    cache = raw ? (JSON.parse(raw) as Watch[]) : seed();
  } catch {
    cache = seed();
  }
  return cache;
}

function publish(next: Watch[]) {
  cache = next;
  listeners.forEach(fn => fn(next));
  AsyncStorage.setItem(KEY, JSON.stringify(next)).catch(() => {});
}

/** In progress, most recent first. */
export function useContinueWatching(): Watch[] {
  const [items, setItems] = useState<Watch[]>(cache ?? []);
  useEffect(() => {
    listeners.add(setItems);
    loadHistory().then(setItems);
    return () => {
      listeners.delete(setItems);
    };
  }, []);
  return items;
}

/** Seconds to resume from (0 = start over). Reads the in-memory copy loaded at startup. */
export function resumeAt(id: string, episode = 0): number {
  return cache?.find(w => w.id === id && w.episode === episode)?.position ?? 0;
}

/** The most recently watched episode of a show, if any. */
export function lastEpisode(id: string): Watch | undefined {
  return cache?.find(w => w.id === id && w.episode > 0);
}

export async function recordWatch(id: string, episode: number, position: number, duration: number) {
  if (!(duration > 0) || !(position >= 0)) {
    return;
  }
  const list = (await loadHistory()).filter(w => !(w.id === id && w.episode === episode));
  // Barely started or basically finished: drop it from Continue Watching.
  if (position >= 10 && position <= duration * 0.95) {
    list.unshift({ id, episode, position: Math.round(position), duration: Math.round(duration), updatedAt: Date.now() });
  }
  publish(list.slice(0, MAX));
}

export function timeLeftLabel(w: Watch): string {
  const mins = Math.max(1, Math.round((w.duration - w.position) / 60));
  const left = mins >= 60 ? `${Math.floor(mins / 60)} hr ${mins % 60} min left` : `${mins} min left`;
  return w.episode > 0 ? `S1, E${w.episode} · ${left}` : left;
}

export function clock(seconds: number): string {
  const s = Math.floor(seconds % 60);
  const m = Math.floor(seconds / 60) % 60;
  const h = Math.floor(seconds / 3600);
  const pad = (n: number) => String(n).padStart(2, '0');
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}

/** Test hook: reset the in-memory cache. */
export function __resetHistoryForTests() {
  cache = null;
  listeners.clear();
}
