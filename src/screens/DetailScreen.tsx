import React, { useRef } from 'react';
import { Image, ScrollView, StyleSheet, Text, View } from 'react-native';
import { episodesFor, getTitle, moreLike } from '../catalog';
import { Button } from '../components/Button';
import { FocusCard } from '../components/FocusCard';
import { colors, layout, s } from '../theme';

type Props = {
  id: string;
  onPlay: (id: string, episode?: number) => void;
  onOpen: (id: string) => void;
};

export function DetailScreen({ id, onPlay, onOpen }: Props) {
  const t = getTitle(id);
  const scroll = useRef<ScrollView>(null);
  const isShow = t.kind === 'show';
  const toTop = () => scroll.current?.scrollTo({ y: 0, animated: true });
  const toShelf = () => scroll.current?.scrollToEnd({ animated: true });

  return (
    <View style={styles.screen}>
      <Image source={t.backdrop} style={styles.backdrop} resizeMethod="resize" />
      <View style={styles.scrim} />

      <ScrollView ref={scroll} scrollEnabled={false} showsVerticalScrollIndicator={false}>
        <View style={styles.top}>
          <Text style={styles.eyebrow}>{isShow ? 'HAUKLEY ORIGINAL SERIES' : 'HAUKLEY ORIGINAL FILM'}</Text>
          <Text style={styles.title}>{t.title}</Text>
          <View style={styles.metaRow}>
            <Badge text={t.rating} />
            <Text style={styles.meta}>
              {t.genre} · {t.year} · {isShow ? `${t.seasons} Season${t.seasons === 1 ? '' : 's'}` : t.runtime}
            </Text>
            <Badge text="4K" />
            <Badge text="HDR" />
            <Badge text="CC" />
          </View>
          <Text style={styles.tagline}>{t.tagline}</Text>
          <Text style={styles.desc}>{t.description}</Text>
          <Text style={styles.credits}>{t.credits}</Text>
          <View style={styles.buttons}>
            <Button
              label={isShow ? 'Play S1, E1' : 'Play'}
              icon="▶"
              hasTVPreferredFocus
              onFocus={toTop}
              onPress={() => onPlay(t.id, isShow ? 1 : undefined)}
            />
            <Button label="Trailer" icon="▶" onFocus={toTop} onPress={() => onPlay(t.id, 99)} />
            <Button label="Up Next" icon="+" round onFocus={toTop} onPress={() => {}} />
          </View>
        </View>

        <Text style={styles.shelfTitle}>{isShow ? 'Season 1' : 'More Like This'}</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.shelf} style={styles.visible}>
          {isShow
            ? episodesFor(t).map(ep => (
                <View key={ep.number} style={styles.item}>
                  <FocusCard
                    source={t.stills?.[ep.number - 1] ?? t.card}
                    width={s(440)}
                    height={s(248)}
                    label={`${ep.number}. ${ep.name}`}
                    sublabel={`${ep.minutes} min`}
                    onFocus={toShelf}
                    onPress={() => onPlay(t.id, ep.number)}
                  />
                </View>
              ))
            : moreLike(t).map(m => (
                <View key={m.id} style={styles.item}>
                  <FocusCard
                    source={m.poster}
                    width={s(220)}
                    height={s(330)}
                    onFocus={toShelf}
                    onPress={() => onOpen(m.id)}
                  />
                </View>
              ))}
        </ScrollView>
        <View style={{ height: s(80) }} />
      </ScrollView>
    </View>
  );
}

function Badge({ text }: { text: string }) {
  return (
    <View style={styles.badge}>
      <Text style={styles.badgeText}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  backdrop: { ...StyleSheet.absoluteFillObject, width: '100%', height: '100%' },
  scrim: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(0,0,0,0.4)' },
  top: { paddingLeft: layout.gutter, paddingTop: s(200), width: s(1100), minHeight: s(700) },
  eyebrow: { color: colors.textDim, fontSize: s(22), fontWeight: '700', letterSpacing: s(3) },
  title: { color: colors.text, fontSize: s(104), fontWeight: '800', letterSpacing: -s(1), marginTop: s(6) },
  metaRow: { flexDirection: 'row', alignItems: 'center', marginTop: s(10), flexWrap: 'wrap' },
  meta: { color: colors.textDim, fontSize: s(26), fontWeight: '600', marginRight: s(16) },
  badge: {
    borderWidth: s(2),
    borderColor: colors.textDim,
    borderRadius: s(6),
    paddingHorizontal: s(8),
    paddingVertical: s(1),
    marginRight: s(12),
  },
  badgeText: { color: colors.textDim, fontSize: s(18), fontWeight: '800' },
  tagline: { color: colors.text, fontSize: s(30), fontWeight: '700', marginTop: s(26) },
  desc: { color: colors.text, fontSize: s(28), lineHeight: s(40), marginTop: s(10), opacity: 0.9 },
  credits: { color: colors.textDim, fontSize: s(24), marginTop: s(14) },
  buttons: { flexDirection: 'row', marginTop: s(40) },
  shelfTitle: { color: colors.text, fontSize: s(34), fontWeight: '700', marginLeft: layout.gutter, marginTop: s(40) },
  visible: { overflow: 'visible' },
  shelf: { paddingHorizontal: layout.gutter, paddingTop: s(30), paddingBottom: s(20) },
  item: { marginRight: s(40) },
});
