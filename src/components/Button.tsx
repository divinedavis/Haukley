import React, { useRef, useState } from 'react';
import { Animated, Pressable, StyleSheet, Text } from 'react-native';
import { colors, s } from '../theme';

type Props = {
  label: string;
  icon?: string;
  onPress: () => void;
  onFocus?: () => void;
  hasTVPreferredFocus?: boolean;
  round?: boolean;
};

// Apple TV pill button: translucent at rest, solid white when focused.
export function Button({ label, icon, onPress, onFocus, hasTVPreferredFocus, round }: Props) {
  const [focused, setFocused] = useState(false);
  const scale = useRef(new Animated.Value(1)).current;
  const animate = (to: number) =>
    Animated.spring(scale, { toValue: to, friction: 7, tension: 120, useNativeDriver: true }).start();

  return (
    <Pressable
      onPress={onPress}
      hasTVPreferredFocus={hasTVPreferredFocus}
      onFocus={() => {
        setFocused(true);
        animate(1.08);
        onFocus?.();
      }}
      onBlur={() => {
        setFocused(false);
        animate(1);
      }}
    >
      <Animated.View
        style={[
          styles.btn,
          round && styles.round,
          { backgroundColor: focused ? colors.pillFocused : colors.pill },
          { transform: [{ scale }] },
          focused && styles.focused,
        ]}
      >
        <Text style={[styles.text, { color: focused ? colors.onPillFocused : colors.text }]}>
          {icon ? `${icon}${round ? '' : '  '}` : ''}
          {round ? '' : label}
        </Text>
      </Animated.View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn: {
    height: s(76),
    paddingHorizontal: s(44),
    borderRadius: s(38),
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: s(20),
  },
  round: { width: s(76), paddingHorizontal: 0 },
  focused: {
    shadowColor: '#000',
    shadowOpacity: 0.5,
    shadowRadius: s(16),
    shadowOffset: { width: 0, height: s(10) },
    elevation: 10,
  },
  text: { fontSize: s(28), fontWeight: '700' },
});
