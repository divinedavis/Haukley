import ads from '../scripts/ads.json';
import { createAdTracker, startPlaybackUrl } from '../src/ads';

type Call = { url: string; body: Record<string, unknown> };
let calls: Call[];

const respond = (handler: (url: string) => { ok: boolean; json?: unknown }) => {
  calls = [];
  (globalThis as unknown as { fetch: unknown }).fetch = jest.fn((url: string, init: { body: string }) => {
    calls.push({ url, body: JSON.parse(init.body) });
    const r = handler(url);
    return Promise.resolve({ ok: r.ok, status: r.ok ? 200 : 500, json: () => Promise.resolve(r.json) });
  });
};

test('start_playback lives next to log_ad_events', () => {
  expect(ads.trackingUrl).toMatch(/\/rpc\/log_ad_events$/);
  expect(startPlaybackUrl(ads.trackingUrl)).toBe(ads.trackingUrl.replace('log_ad_events', 'start_playback'));
});

test('events carry the signed ticket and a fresh seq each', async () => {
  respond(url =>
    url.endsWith('start_playback')
      ? { ok: true, json: { session_id: 'srv-session', token: '1790000000.' + 'a'.repeat(64) } }
      : { ok: true },
  );
  const tracker = createAdTracker('metropolis', 0);
  await tracker.log('ad_started');
  await tracker.log('ad_completed');
  expect(calls[0]).toMatchObject({ url: expect.stringMatching(/start_playback$/), body: { title_id: 'metropolis', episode: 0 } });
  const events = calls.filter(c => c.url.endsWith('log_ad_events')).map(c => c.body);
  expect(events).toEqual([
    expect.objectContaining({ event: 'ad_started', session_id: 'srv-session', seq: 1, token: expect.any(String) }),
    expect.objectContaining({ event: 'ad_completed', session_id: 'srv-session', seq: 2, token: expect.any(String) }),
  ]);
});

test('without a ticket events still go out, tokenless, never throwing', async () => {
  respond(url => (url.endsWith('start_playback') ? { ok: false } : { ok: true }));
  const tracker = createAdTracker('metropolis', 2);
  await expect(tracker.log('ad_started')).resolves.toBeUndefined();
  const ev = calls.find(c => c.url.endsWith('log_ad_events'))!.body;
  expect(ev).toMatchObject({ event: 'ad_started', episode: 2 });
  expect(ev.session_id).toMatch(/^[0-9a-f-]{36}$/);
  expect(ev).not.toHaveProperty('token');
});

test('a retry resends the same seq (server drops the duplicate)', async () => {
  jest.useFakeTimers();
  let n = 0;
  respond(url =>
    url.endsWith('start_playback')
      ? { ok: true, json: { session_id: 's', token: 't' } }
      : { ok: n++ > 0 },
  );
  const tracker = createAdTracker('metropolis', 0);
  const p = tracker.log('ad_completed');
  await jest.advanceTimersByTimeAsync(3500);
  await p;
  const sent = calls.filter(c => c.url.endsWith('log_ad_events')).map(c => c.body.seq);
  expect(sent).toEqual([1, 1]);
  jest.useRealTimers();
});
