import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import Video, { type VideoRef } from 'react-native-video';
import { TRAILER, adTagFor, createAdTracker } from '../ads';
import { getTitle, streamFor } from '../catalog';
import { recordWatch } from '../history';
import { colors, layout, s } from '../theme';

type Props = { id: string; episode?: number; startAt?: number; onDone: () => void };

export function PlayerScreen({ id, episode, startAt, onDone }: Props) {
  const video = useRef<VideoRef>(null);
  // Last content position and duration, saved on the way out for Continue Watching.
  const progress = useRef({ position: 0, duration: 0 });
  const resumed = useRef(false);
  const t = getTitle(id);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Content advisory card, shown for 8 s once the film itself starts (not during an ad).
  const [advisory, setAdvisory] = useState(false);
  const advisoryShown = useRef(false);
  // The LIVE tag shows for the first seconds of a live channel, then gets out of the way
  // (the channel's own picture carries its on-air tag).
  const [liveTag, setLiveTag] = useState(true);
  useEffect(() => {
    if (!advisory) {
      return;
    }
    const timer = setTimeout(() => setAdvisory(false), 8000);
    return () => clearTimeout(timer);
  }, [advisory]);
  const isTrailer = episode === TRAILER;
  // A live channel: no ads, no resume seek, no saved position, and no scrubber.
  const live = t.kind === 'live';
  const noAds = isTrailer || live;
  // One server-signed session per playback groups its ad events (only those count toward
  // payouts); the ad tag carries title_id for the ad server's report. Trailers and live
  // channels have no ads.
  const tracker = useMemo(() => (noAds ? null : createAdTracker(id, episode ?? 0)), [id, episode, noAds]);
  const adCounted = useRef(false);
  const source = useMemo(
    () => ({
      uri: streamFor(id, episode),
      ...(noAds ? {} : { ad: { type: 'csai' as const, adTagUrl: adTagFor(t) } }),
    }),
    [id, episode, noAds, t],
  );
  useEffect(() => {
    // The ref object itself is stable; read its latest value when the player closes.
    const last = progress;
    return () => {
      if (!isTrailer && !live) {
        recordWatch(id, episode ?? 0, last.current.position, last.current.duration);
      }
    };
  }, [id, episode, isTrailer, live]);

  useEffect(() => {
    if (!live || loading) {
      return;
    }
    const timer = setTimeout(() => setLiveTag(false), 6000);
    return () => clearTimeout(timer);
  }, [live, loading]);

  const subtitle = isTrailer ? 'Official Trailer' : live ? 'Live' : episode ? `Episode ${episode}` : t.genre;

  return (
    <View style={styles.screen}>
      {!error && (
        <Video
          source={source}
          style={StyleSheet.absoluteFill}
          resizeMode="contain"
          controls={!live}
          // ExoPlayer pins its own LIVE label over the picture; ours times out instead.
          controlsStyles={{ hideLiveBadge: true }}
          ref={video}
          onLoad={e => {
            setLoading(false);
            if (e.duration > 0) {
              progress.current.duration = e.duration;
            }
          }}
          // With IMA ads on Android, onLoad never fires for the content, so duration and the
          // resume seek both come from progress events, which do arrive once content plays.
          onProgress={e => {
            if (t.advisory && !isTrailer && !advisoryShown.current && e.currentTime > 0.5) {
              advisoryShown.current = true;
              setAdvisory(true);
            }
            progress.current.position = e.currentTime;
            if (e.seekableDuration > 0) {
              progress.current.duration = e.seekableDuration;
            }
            if (!live && startAt && startAt > 0 && !resumed.current) {
              resumed.current = true;
              video.current?.seek(startAt);
            }
          }}
          onReceiveAdEvent={e => {
            if (e.event === 'CONTENT_PAUSE_REQUESTED') {
              setLoading(false);
            } else if (e.event === 'STARTED' || e.event === 'FIRST_QUARTILE') {
              // Android drops STARTED for the first ad after a cold start, so FIRST_QUARTILE backs it up.
              if (!adCounted.current) {
                adCounted.current = true;
                tracker?.log('ad_started');
              }
            } else if (e.event === 'COMPLETED') {
              adCounted.current = false;
              tracker?.log('ad_completed');
            } else if (e.event === 'SKIPPED') {
              adCounted.current = false;
            }
          }}
          onError={e => setError(JSON.stringify(e.error?.errorString ?? e.error ?? e).slice(0, 200))}
          onEnd={onDone}
        />
      )}
      {live && liveTag && !loading && !error && (
        <View style={styles.live} pointerEvents="none" testID="live-badge">
          <Text style={styles.liveText}>LIVE</Text>
        </View>
      )}
      {advisory && (
        <View style={styles.advisory} pointerEvents="none">
          <Text style={styles.advisoryLabel}>ADVISORY</Text>
          <Text style={styles.advisoryText}>{t.advisory}</Text>
        </View>
      )}
      {(loading || error) && (
        <View style={styles.overlay}>
          <Text style={styles.title}>{t.title}</Text>
          <Text style={styles.subtitle}>{subtitle}</Text>
          {error ? (
            <Text style={styles.error}>Couldn’t play this stream. Press Back to return.{'\n'}{error}</Text>
          ) : (
            <ActivityIndicator size="large" color={colors.text} style={{ marginTop: s(30) }} />
          )}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#000' },
  overlay: { ...StyleSheet.absoluteFillObject, justifyContent: 'center', paddingLeft: layout.gutter },
  title: { color: colors.text, fontSize: s(72), fontWeight: '800' },
  subtitle: { color: colors.textDim, fontSize: s(30), marginTop: s(6) },
  advisory: {
    position: 'absolute', top: '22%', left: 0, paddingVertical: s(10), paddingLeft: s(28), paddingRight: s(36),
    borderLeftWidth: s(6), borderLeftColor: colors.accent, backgroundColor: 'rgba(0,0,0,0.55)', maxWidth: s(1000),
  },
  advisoryLabel: { color: colors.text, fontSize: s(30), fontWeight: '800', letterSpacing: 1 },
  advisoryText: { color: colors.textDim, fontSize: s(24), marginTop: s(4) },
  live: { position: 'absolute', top: s(48), right: s(64), backgroundColor: colors.live, borderRadius: s(8), paddingHorizontal: s(16), paddingVertical: s(6) },
  liveText: { color: '#fff', fontSize: s(26), fontWeight: '800', letterSpacing: s(2) },
  error: { color: '#ff8a80', fontSize: s(24), marginTop: s(30), width: s(1200) },
});
