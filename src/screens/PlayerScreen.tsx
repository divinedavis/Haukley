import React, { useMemo, useRef, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import Video from 'react-native-video';
import { TRAILER, adTagFor, logAdEvent, newSessionId } from '../ads';
import { getTitle, streamFor } from '../catalog';
import { colors, layout, s } from '../theme';

type Props = { id: string; episode?: number; onDone: () => void };

export function PlayerScreen({ id, episode, onDone }: Props) {
  const t = getTitle(id);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isTrailer = episode === TRAILER;
  // One session per playback groups its ad events; the ad tag carries title_id for the ad server's report.
  const sessionId = useMemo(newSessionId, []);
  const adCounted = useRef(false);
  const source = useMemo(
    () => ({
      uri: streamFor(id, episode),
      ...(isTrailer ? {} : { ad: { type: 'csai' as const, adTagUrl: adTagFor(t) } }),
    }),
    [id, episode, isTrailer, t],
  );
  const subtitle = isTrailer ? 'Official Trailer' : episode ? `Season 1, Episode ${episode}` : t.genre;

  return (
    <View style={styles.screen}>
      {!error && (
        <Video
          source={source}
          style={StyleSheet.absoluteFill}
          resizeMode="contain"
          controls
          onLoad={() => setLoading(false)}
          onReceiveAdEvent={e => {
            const ep = episode ?? 0;
            if (e.event === 'CONTENT_PAUSE_REQUESTED') {
              setLoading(false);
            } else if (e.event === 'STARTED' || e.event === 'FIRST_QUARTILE') {
              // Android drops STARTED for the first ad after a cold start, so FIRST_QUARTILE backs it up.
              if (!adCounted.current) {
                adCounted.current = true;
                logAdEvent(id, ep, 'ad_started', sessionId);
              }
            } else if (e.event === 'COMPLETED') {
              adCounted.current = false;
              logAdEvent(id, ep, 'ad_completed', sessionId);
            } else if (e.event === 'SKIPPED') {
              adCounted.current = false;
            }
          }}
          onError={e => setError(JSON.stringify(e.error?.errorString ?? e.error ?? e).slice(0, 200))}
          onEnd={onDone}
        />
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
  error: { color: '#ff8a80', fontSize: s(24), marginTop: s(30), width: s(1200) },
});
