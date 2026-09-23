import React, { useCallback, useMemo, useRef, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { FEATURED, MOVIES, ROWS, SHOWS } from '../catalog';
import { Hero, HERO_HEIGHT, HERO_OVERLAP } from '../components/Hero';
import { Shelf } from '../components/Shelf';
import { Tab, TopNav } from '../components/TopNav';
import { colors, s } from '../theme';

type Props = {
  active: boolean;
  onOpen: (id: string) => void;
  onPlay: (id: string, episode?: number) => void;
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
  const rows = ROWS[tab];

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
                onSelect={(id, ep) => (row.type === 'upNext' ? onPlay(id, ep) : onOpen(id))}
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
