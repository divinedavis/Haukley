import { Platform } from 'react-native';
import ads from '../scripts/ads.json';
import type { Title } from './types';

// Trailers (episode 99) play without ads.
export const TRAILER = 99;

export const adTagFor = (t: Title) =>
  ads.adTagTemplate
    .replace('{TITLE_ID}', encodeURIComponent(t.id))
    .replace('{KIND}', t.kind)
    .replace('{CORRELATOR}', String(Date.now()));

const platform = Platform.isTVOS
  ? 'tvos'
  : (Platform.constants as { Manufacturer?: string }).Manufacturer === 'Amazon'
    ? 'firetv'
    : 'androidtv';

// Hermes has no crypto.randomUUID; a v4-shaped id is enough to group one viewing.
export const newSessionId = () =>
  'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.floor(Math.random() * 16);
    return (c === 'x' ? r : 8 + (r % 4)).toString(16);
  });

type AdEvent = 'ad_started' | 'ad_completed';

// Fire-and-forget with one retry: a tracking failure must never interrupt playback.
export function logAdEvent(titleId: string, episode: number, event: AdEvent, sessionId: string) {
  const body = JSON.stringify({ title_id: titleId, episode, platform, event, session_id: sessionId });
  const send = () =>
    fetch(ads.trackingUrl, {
      method: 'POST',
      headers: {
        apikey: ads.publishableKey,
        'Content-Type': 'application/json',
        Prefer: 'return=minimal',
      },
      body,
    }).then(r => {
      if (!r.ok) {
        throw new Error(String(r.status));
      }
    });
  send()
    .catch(() => new Promise<void>(res => setTimeout(() => res(), 3000)).then(send))
    .catch(() => {});
}
