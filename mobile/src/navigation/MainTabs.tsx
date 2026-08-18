import { createBottomTabNavigator } from '@react-navigation/bottom-tabs'
import { Ionicons } from '@expo/vector-icons'
import { HomeScreen } from '../screens/HomeScreen'
import { MoreScreen } from '../screens/MoreScreen'
import { Placeholder } from '../screens/Placeholder'
import { ReportsStack } from './ReportsStack'
import { ContactsStack } from './ContactsStack'
import { colors, font } from '../theme'

const Tab = createBottomTabNavigator()

const MarketScreen = () => (
  <Placeholder title="بازار و گفتگو" note="اتصال‌ها، سفارش‌ها و چتِ فروشگاه↔پخش در نسخه‌ی بعدی." />
)

type IconName = keyof typeof Ionicons.glyphMap
const ICONS: Record<string, IconName> = {
  Home: 'home',
  Reports: 'stats-chart',
  Market: 'chatbubbles',
  Contacts: 'people',
  More: 'menu',
}

export function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.textFaint,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
          height: 62,
          paddingBottom: 8,
          paddingTop: 6,
        },
        tabBarLabelStyle: { fontSize: font.size.xs, fontWeight: font.weight.semibold },
        tabBarIcon: ({ color, size }) => (
          <Ionicons name={ICONS[route.name] ?? 'ellipse'} size={size} color={color} />
        ),
      })}
    >
      <Tab.Screen name="Home" component={HomeScreen} options={{ title: 'خانه' }} />
      <Tab.Screen name="Reports" component={ReportsStack} options={{ title: 'گزارش' }} />
      <Tab.Screen name="Market" component={MarketScreen} options={{ title: 'بازار' }} />
      <Tab.Screen name="Contacts" component={ContactsStack} options={{ title: 'اشخاص' }} />
      <Tab.Screen name="More" component={MoreScreen} options={{ title: 'بیشتر' }} />
    </Tab.Navigator>
  )
}
