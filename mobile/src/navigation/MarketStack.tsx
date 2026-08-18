import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { MarketHomeScreen } from '../screens/market/MarketHomeScreen'
import { ChatScreen } from '../screens/market/ChatScreen'
import { colors, font } from '../theme'
import type { MarketStackParams } from './types'

const Stack = createNativeStackNavigator<MarketStackParams>()

export function MarketStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.surface },
        headerTintColor: colors.text,
        headerTitleStyle: { fontWeight: font.weight.bold },
        contentStyle: { backgroundColor: colors.bg },
        headerShadowVisible: false,
      }}
    >
      <Stack.Screen name="MarketHome" component={MarketHomeScreen} options={{ headerShown: false }} />
      <Stack.Screen name="Chat" component={ChatScreen} options={({ route }) => ({ title: route.params.title ?? 'گفتگو' })} />
    </Stack.Navigator>
  )
}
