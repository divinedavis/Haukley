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

type Ticket = { session_id: string; token: string };

const post = (url: string, body: string) =>
  fetch(url, {
    method: 'POST',
    headers: { apikey: ads.publishableKey, 'Content-Type': 'application/json', Prefer: 'return=minimal' },
    body,
  }).then(r => {
    if (!r.ok) {
      throw new Error(String(r.status));
    }
    return r;
  });

// The server-signed playback ticket comes from start_playback (same API as log_ad_events).
export const startPlaybackUrl = (trackingUrl: string) =>
  trackingUrl.replace(/log_ad_events$/, 'start_playback');

/**
 * One tracker per playback. It asks the server for a signed playback ticket as soon as the
 * player opens; only events carrying that ticket count toward filmmaker payouts. Every event
 * gets its own seq, so the one retry below can never be counted twice. If the ticket request
 * fails, events still go out (stored, not counted) under a local session id.
 * Fire-and-forget: tracking must never interrupt playback.
 */
export function createAdTracker(titleId: string, episode: number) {
  const fallbackSession = newSessionId();
  const ticket: Promise<Ticket | null> = post(
    startPlaybackUrl(ads.trackingUrl),
    JSON.stringify({ title_id: titleId, episode, platform }),
  )
    .then(r => r.json() as Promise<Ticket>)
    .then(t => (t && t.session_id && t.token ? t : null))
    .catch(() => null);
  let seq = 0;
  return {
    ticket,
    log(event: AdEvent): Promise<void> {
      seq += 1;
      const mySeq = seq;
      return ticket
        .then(t => {
          const body = JSON.stringify({
            title_id: titleId,
            episode,
            platform,
            event,
            session_id: t ? t.session_id : fallbackSession,
            ...(t ? { token: t.token, seq: mySeq } : {}),
          });
          return post(ads.trackingUrl, body)
            .catch(() => new Promise<void>(res => setTimeout(() => res(), 3000)).then(() => post(ads.trackingUrl, body)))
            .then(() => undefined);
        })
        .catch(() => {});
    },
  };
}
