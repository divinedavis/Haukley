import React, { useCallback, useEffect, useState } from 'react';
import { BackHandler, Platform, Settings, StatusBar, StyleSheet, TVEventControl, View } from 'react-native';
import { DetailScreen } from './src/screens/DetailScreen';
import { HomeScreen } from './src/screens/HomeScreen';
import { PlayerScreen } from './src/screens/PlayerScreen';
import { loadCatalog, refreshCatalog } from './src/catalog';
import type { Route } from './src/types';

// Minimal stack navigator. Home stays mounted (hidden) under other screens so
// its scroll position and focus survive a round trip to a detail page.
// Store screenshots: `simctl launch <sim> com.haukley.app -HKOpen detail:<id>` (or player:<id>)
// opens that screen on top of Home. Launch arguments land in NSUserDefaults, which Settings
// reads; nothing sets this key otherwise, so normal launches are unaffected.
function initialStack(): Route[] {
  let open: unknown;
  try {
    open = Platform.OS === 'ios' ? Settings.get('HKOpen') : undefined;
  } catch {
    // No native Settings module (unit tests): start on Home.
  }
  const [screen, id] = typeof open === 'string' ? open.split(':') : [];
  if (id && screen === 'detail') {
    return [{ name: 'home' }, { name: 'detail', id }];
  }
  if (id && screen === 'player') {
    return [{ name: 'home' }, { name: 'detail', id }, { name: 'player', id }];
  }
  return [{ name: 'home' }];
}

function App() {
  const [stack, setStack] = useState<Route[]>(initialStack);
  // Swap in the live catalog saved last launch before the first screen renders, then fetch
  // the next one in the background (it applies on the following launch).
  const [ready, setReady] = useState(false);
  useEffect(() => {
    loadCatalog().finally(() => setReady(true));
    refreshCatalog();
  }, []);
  const push = useCallback((r: Route) => setStack(st => [...st, r]), []);
  const pop = useCallback(() => setStack(st => (st.length > 1 ? st.slice(0, -1) : st)), []);

  // The tvOS Menu button must exit the app at the root, so only capture it deeper in.
  useEffect(() => {
    if (Platform.isTVOS) {
      if (stack.length > 1) {
        TVEventControl.enableTVMenuKey();
      } else {
        TVEventControl.disableTVMenuKey();
      }
    }
  }, [stack.length]);

  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      if (stack.length > 1) {
        pop();
        return true;
      }
      return false;
    });
    return () => sub.remove();
  }, [stack.length, pop]);

  const top = stack[stack.length - 1];
  if (!ready) {
    return <View style={styles.root} />;
  }
  const openDetail = (id: string) => push({ name: 'detail', id });
  const play = (id: string, episode?: number, startAt?: number) => push({ name: 'player', id, episode, startAt });

  return (
    <View style={styles.root}>
      <StatusBar hidden />
      <View style={[styles.fill, top.name !== 'home' && styles.hidden]}>
        <HomeScreen active={top.name === 'home'} onOpen={openDetail} onPlay={play} />
      </View>
      {stack.slice(1).map((r, i) => {
        const isTop = i === stack.length - 2;
        return (
          <View key={`${r.name}-${i}`} style={[styles.fill, !isTop && styles.hidden]}>
            {r.name === 'detail' && <DetailScreen id={r.id} onPlay={play} onOpen={openDetail} />}
            {r.name === 'player' && <PlayerScreen id={r.id} episode={r.episode} startAt={r.startAt} onDone={pop} />}
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#000' },
  fill: { ...StyleSheet.absoluteFillObject },
  hidden: { display: 'none' },
});

export default App;
