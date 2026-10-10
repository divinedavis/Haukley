import React from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { colors, s } from '../theme';
import { errorText, placeLabel, type LocalWeather, type Place, type WeatherError } from '../weather';

type Props = {
  place: Place | null;
  weather: LocalWeather | null;
  error: WeatherError | null;
  loading: boolean;
};

// "Your weather" on the Haukley Weather title page: the viewer's own forecast next to the
// national channel. Display only; the "Change city" button lives with the other buttons.
export function WeatherCard({ place, weather, error, loading }: Props) {
  return (
    <View style={styles.card} testID="weather-card">
      <Text style={styles.eyebrow}>YOUR WEATHER</Text>
      {loading && !weather ? (
        <ActivityIndicator color={colors.text} style={{ marginTop: s(30) }} />
      ) : weather ? (
        <>
          <Text style={styles.place} numberOfLines={1}>{weather.place.name}</Text>
          <View style={styles.nowRow}>
            <Text style={styles.temp}>{Math.round(weather.now.temp)}°</Text>
            <View style={styles.nowText}>
              <Text style={styles.cond} numberOfLines={2}>{weather.now.text}</Text>
              {weather.now.wind ? <Text style={styles.dim}>Wind {weather.now.wind}</Text> : null}
            </View>
          </View>
          {weather.alerts.length ? (
            <View style={styles.alert} testID="weather-alert">
              <Text style={styles.alertText} numberOfLines={2}>
                ⚠ {weather.alerts[0].event}
                {weather.alerts.length > 1 ? ` +${weather.alerts.length - 1} more` : ''}
              </Text>
            </View>
          ) : null}
          <View style={styles.periods}>
            {weather.periods.slice(0, 4).map(p => (
              <View key={p.name} style={styles.period}>
                <Text style={[styles.pName, { color: p.day ? colors.accent : colors.textDim }]} numberOfLines={1}>
                  {p.name}
                </Text>
                <Text style={styles.pTemp}>{Math.round(p.temp)}°</Text>
                <Text style={styles.pText} numberOfLines={2}>{p.text}</Text>
              </View>
            ))}
          </View>
          <Text style={styles.attr} numberOfLines={1}>
            {place ? `${placeLabel(place)} · ` : ''}
            {weather.attribution ?? 'NOAA / National Weather Service'}
          </Text>
        </>
      ) : (
        <Text style={styles.error}>{errorText(error ?? 'unavailable')}</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    width: s(620),
    padding: s(32),
    borderRadius: s(20),
    backgroundColor: 'rgba(12,10,30,0.78)',
    borderWidth: s(1),
    borderColor: 'rgba(255,255,255,0.12)',
  },
  eyebrow: { color: colors.textDim, fontSize: s(20), fontWeight: '800', letterSpacing: s(3) },
  place: { color: colors.text, fontSize: s(40), fontWeight: '800', marginTop: s(6) },
  nowRow: { flexDirection: 'row', alignItems: 'center', marginTop: s(6) },
  temp: { color: colors.text, fontSize: s(110), fontWeight: '300', marginRight: s(20) },
  nowText: { flex: 1 },
  cond: { color: colors.text, fontSize: s(30), fontWeight: '600' },
  dim: { color: colors.textDim, fontSize: s(22), marginTop: s(6) },
  alert: { backgroundColor: colors.live, borderRadius: s(10), paddingHorizontal: s(14), paddingVertical: s(8), marginTop: s(10) },
  alertText: { color: '#fff', fontSize: s(22), fontWeight: '700' },
  periods: { flexDirection: 'row', marginTop: s(20) },
  period: { flex: 1, marginRight: s(12) },
  pName: { fontSize: s(19), fontWeight: '800' },
  pTemp: { color: colors.text, fontSize: s(40), fontWeight: '600', marginTop: s(4) },
  pText: { color: colors.textDim, fontSize: s(18), marginTop: s(2) },
  attr: { color: colors.textFaint, fontSize: s(16), marginTop: s(18) },
  error: { color: colors.textDim, fontSize: s(24), marginTop: s(16), lineHeight: s(34) },
});
