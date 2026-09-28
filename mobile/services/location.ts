import * as Location from 'expo-location';

export async function getCurrentLocation() {
  const { status } = await Location.requestForegroundPermissionsAsync();
  if (status !== 'granted') throw new Error('Location permission denied');
  const { coords } = await Location.getCurrentPositionAsync({});
  return { lat: coords.latitude, lon: coords.longitude };
}
