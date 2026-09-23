import React, { useCallback, useEffect, useState } from 'react';
import { BackHandler, Platform, StatusBar, StyleSheet, TVEventControl, View } from 'react-native';
import { DetailScreen } from './src/screens/DetailScreen';
import { HomeScreen } from './src/screens/HomeScreen';
import { PlayerScreen } from './src/screens/PlayerScreen';
import type { Route } from './src/types';

// Minimal stack navigator. Home stays mounted (hidden) under other screens so
// its scroll position and focus survive a round trip to a detail page.
function App() {
  const [stack, setStack] = useState<Route[]>([{ name: 'home' }]);
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
  const openDetail = (id: string) => push({ name: 'detail', id });
  const play = (id: string, episode?: number) => push({ name: 'player', id, episode });

  return (
    <View style={styles.root}>
      <StatusBar hidden />
      <View style={[styles.fill, top.name !== 'home' && styles.hidden]}>
        <HomeScreen onOpen={openDetail} onPlay={play} />
      </View>
      {stack.slice(1).map((r, i) => {
        const isTop = i === stack.length - 2;
        return (
          <View key={`${r.name}-${i}`} style={[styles.fill, !isTop && styles.hidden]}>
            {r.name === 'detail' && <DetailScreen id={r.id} onPlay={play} onOpen={openDetail} />}
            {r.name === 'player' && <PlayerScreen id={r.id} episode={r.episode} onDone={pop} />}
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
