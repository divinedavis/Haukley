import React, { useCallback, useMemo, useRef, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { FEATURED, MOVIES, ROWS, SHOWS, getTitle, hasTitle, type Row } from '../catalog';
import { Hero, HERO_HEIGHT, HERO_OVERLAP } from '../components/Hero';
import { Shelf } from '../components/Shelf';
import { Tab, TopNav } from '../components/TopNav';
import { resumeAt, timeLeftLabel, useContinueWatching } from '../history';
import { colors, s } from '../theme';

type Props = {
  active: boolean;
  onOpen: (id: string) => void;
  onPlay: (id: string, episode?: number, startAt?: number) => void;
};

export function HomeScreen({ active, onOpen, onPlay }: Props) {
  const [tab, setTab] = useState<Tab>('home');
  const scroll = useRef<ScrollView>(null);
  const rowY = useRef<Record<string, number>>({});
  // Where focus was when we left, so coming back from the hero lands on Play again
  // (rows restore focus on their own).
  const [focusArea, setFocusArea] = useState<'hero' | 'rows'>('hero');

  const hero = useMemo(
    () => (tab === 'movies' ? MOVIES.slice(0, 5) : tab === 'shows' ? SHOWS.slice(0, 5) : FEATURED),
    [tab],
  );
  const watching = useContinueWatching();
  // Up Next comes from what this TV has actually been watching (seeded on first run).
  const rows = useMemo<Row[]>(
    () =>
      ROWS[tab].flatMap((r): Row[] => {
        if (r.type !== 'upNext') {
          return [r];
        }
        // History can name titles no longer in the catalog (older builds): skip those.
        const items = watching.filter(w => hasTitle(w.id)).map(w => ({
          title: getTitle(w.id),
          label: timeLeftLabel(w),
          progress: w.duration > 0 ? w.position / w.duration : 0,
          episode: w.episode || undefined,
        }));
        return items.length ? [{ ...r, items }] : [];
      }),
    [tab, watching],
  );

  const toTop = useCallback(() => {
    setFocusArea('hero');
    scroll.current?.scrollTo({ y: 0, animated: true });
  }, []);
  // Keep the focused shelf pinned near the top of the screen, as tvOS does.
  const toRow = useCallback((key: string) => {
    setFocusArea('rows');
    const y = rowY.current[key];
    if (y !== undefined) {
      scroll.current?.scrollTo({ y: Math.max(0, y - s(70)), animated: true });
    }
  }, []);

  return (
    <View style={styles.screen}>
      <ScrollView ref={scroll} showsVerticalScrollIndicator={false} scrollEnabled={false}>
        <Hero items={hero} onPlay={id => onPlay(id)} onInfo={onOpen} onFocus={toTop} preferredFocus={active && focusArea === 'hero'} />
        {/* Inside the scroll view so it scrolls away with the hero, like the Apple TV app. */}
        <TopNav tab={tab} onChange={setTab} onFocus={toTop} />
        <View style={styles.rows}>
          {rows.map(row => (
            <View
              key={row.key}
              onLayout={e => {
                rowY.current[row.key] = HERO_HEIGHT - HERO_OVERLAP + e.nativeEvent.layout.y;
              }}
            >
              <Shelf
                row={row}
                onFocusRow={() => toRow(row.key)}
                onSelect={(id, ep) => (row.type === 'upNext' ? onPlay(id, ep, resumeAt(id, ep ?? 0)) : onOpen(id))}
              />
            </View>
          ))}
        </View>
        <View style={{ height: s(400) }} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  // Pull the first shelf up over the hero's faded bottom edge.
  rows: { marginTop: -HERO_OVERLAP },
});
