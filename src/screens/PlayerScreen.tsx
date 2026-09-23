import React, { useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import Video from 'react-native-video';
import { getTitle, streamFor } from '../catalog';
import { colors, layout, s } from '../theme';

type Props = { id: string; episode?: number; onDone: () => void };

export function PlayerScreen({ id, episode, onDone }: Props) {
  const t = getTitle(id);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const subtitle = episode === 99 ? 'Official Trailer' : episode ? `Season 1, Episode ${episode}` : t.genre;

  return (
    <View style={styles.screen}>
      {!error && (
        <Video
          source={{ uri: streamFor(id, episode) }}
          style={StyleSheet.absoluteFill}
          resizeMode="contain"
          controls
          onLoad={() => setLoading(false)}
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
