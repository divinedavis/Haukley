import React, { useEffect, useRef, useState } from 'react';
import { Animated, Image, StyleSheet, Text, View } from 'react-native';
import type { Title } from '../types';
import { colors, layout, s } from '../theme';
import { Button } from './Button';

type Props = {
  items: Title[];
  onPlay: (id: string) => void;
  onInfo: (id: string) => void;
  onFocus: () => void;
  preferredFocus?: boolean;
};

// Full screen height so the baked-in bottom fade reaches black before the shelves.
export const HERO_HEIGHT = s(1080);
export const HERO_OVERLAP = s(300);

// Full-bleed featured carousel that crossfades every 8 seconds.
export function Hero({ items, onPlay, onInfo, onFocus, preferredFocus }: Props) {
  const [index, setIndex] = useState(0);
  const [prev, setPrev] = useState<number | null>(null);
  const fade = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    setIndex(0);
    setPrev(null);
  }, [items]);

  useEffect(() => {
    const id = setInterval(() => {
      setIndex(i => {
        setPrev(i);
        return (i + 1) % items.length;
      });
    }, 8000);
    return () => clearInterval(id);
  }, [items]);

  useEffect(() => {
    fade.setValue(0);
    // JS driver: native-driven opacity stalls on Fire OS after the view is hidden.
    Animated.timing(fade, { toValue: 1, duration: 900, useNativeDriver: false }).start();
  }, [index, fade]);

  const t = items[index];
  return (
    <View style={styles.hero}>
      {prev !== null && <Image source={items[prev].backdrop} style={styles.backdrop} resizeMethod="resize" />}
      <Animated.View style={[styles.backdrop, { opacity: fade }]}>
        <Image source={t.backdrop} style={styles.backdrop} resizeMethod="resize" />
      </Animated.View>

      <Animated.View style={[styles.info, { opacity: fade }]}>
        <Text style={styles.eyebrow}>{t.kind === 'show' ? 'NEW SEASON' : 'NOW STREAMING'}</Text>
        <Text style={styles.title} numberOfLines={2}>
          {t.title}
        </Text>
        <Text style={styles.meta}>
          {t.genre} · {t.year} · {t.rating}
          {t.kind === 'show' ? ` · ${t.seasons} Season${t.seasons === 1 ? '' : 's'}` : ` · ${t.runtime}`}
        </Text>
        <Text style={styles.desc} numberOfLines={2}>
          {t.description}
        </Text>
        <View style={styles.buttons}>
          <Button
            label={t.kind === 'show' ? 'Play S1, E1' : 'Play'}
            icon="▶"
            hasTVPreferredFocus={preferredFocus}
            onFocus={onFocus}
            onPress={() => onPlay(t.id)}
          />
          <Button label="Details" icon="ⓘ" onFocus={onFocus} onPress={() => onInfo(t.id)} />
        </View>
      </Animated.View>

      <View style={styles.dots}>
        {items.map((it, i) => (
          <View key={it.id} style={[styles.dot, i === index && styles.dotActive]} />
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  hero: { height: HERO_HEIGHT, width: '100%', backgroundColor: colors.bg },
  backdrop: { ...StyleSheet.absoluteFillObject, width: '100%', height: '100%' },
  info: { position: 'absolute', left: layout.gutter, bottom: s(380), width: s(900) },
  eyebrow: { color: colors.textDim, fontSize: s(22), fontWeight: '700', letterSpacing: s(3), marginBottom: s(8) },
  title: { color: colors.text, fontSize: s(96), fontWeight: '800', letterSpacing: -s(1) },
  meta: { color: colors.textDim, fontSize: s(26), fontWeight: '600', marginTop: s(6) },
  desc: { color: colors.text, fontSize: s(28), lineHeight: s(38), marginTop: s(14), opacity: 0.9 },
  buttons: { flexDirection: 'row', marginTop: s(34) },
  dots: { position: 'absolute', right: layout.gutter, bottom: s(394), flexDirection: 'row' },
  dot: { width: s(10), height: s(10), borderRadius: s(5), backgroundColor: 'rgba(255,255,255,0.35)', marginLeft: s(10) },
  dotActive: { backgroundColor: colors.text, width: s(28) },
});
