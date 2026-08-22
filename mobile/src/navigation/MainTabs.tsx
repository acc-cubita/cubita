import { createBottomTabNavigator } from '@react-navigation/bottom-tabs'
import { Ionicons } from '@expo/vector-icons'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useQuery } from '@tanstack/react-query'
import { HomeStack } from './HomeStack'
import { MoreScreen } from '../screens/MoreScreen'
import { ReportsStack } from './ReportsStack'
import { ContactsStack } from './ContactsStack'
import { MarketStack } from './MarketStack'
import { useAuth } from '../auth/AuthContext'
import { fetchUnread } from '../api/marketplace'
import { colors, font } from '../theme'

const Tab = createBottomTabNavigator()

type IconName = keyof typeof Ionicons.glyphMap
const ICONS: Record<string, IconName> = {
  Home: 'home',
  Reports: 'stats-chart',
  Market: 'chatbubbles',
  Contacts: 'people',
  More: 'menu',
}

export function MainTabs() {
  const { me } = useAuth()
  // insetِ پایینِ اندروید (نوارِ ناوبری/ژست). بدونِ این، نوارِ تب زیرِ نوارِ سیستم می‌افتد.
  const insets = useSafeAreaInsets()
  const isMarket = me?.tenant_kind === 'distributor' || me?.tenant_kind === 'retailer'

  // نشانِ خوانده‌نشده‌ی چتِ بازار روی تبِ «بازار» — پولِ سبک هر ~۲۵ ثانیه.
  const unreadQ = useQuery({
    queryKey: ['mp-unread'],
    queryFn: fetchUnread,
    enabled: isMarket,
    refetchInterval: 25_000,
  })
  const unread = isMarket ? unreadQ.data ?? 0 : 0

  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.textFaint,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
          height: 62 + insets.bottom,
          paddingBottom: 8 + insets.bottom,
          paddingTop: 6,
        },
        tabBarLabelStyle: { fontSize: font.size.xs, fontWeight: font.weight.semibold },
        tabBarIcon: ({ color, size }) => (
          <Ionicons name={ICONS[route.name] ?? 'ellipse'} size={size} color={color} />
        ),
      })}
    >
      <Tab.Screen name="Home" component={HomeStack} options={{ title: 'خانه' }} />
      <Tab.Screen name="Reports" component={ReportsStack} options={{ title: 'گزارش' }} />
      <Tab.Screen
        name="Market"
        component={MarketStack}
        options={{ title: 'بازار', tabBarBadge: unread > 0 ? (unread > 99 ? '۹۹+' : unread.toLocaleString('fa-IR')) : undefined }}
      />
      <Tab.Screen name="Contacts" component={ContactsStack} options={{ title: 'اشخاص' }} />
      <Tab.Screen name="More" component={MoreScreen} options={{ title: 'بیشتر' }} />
    </Tab.Navigator>
  )
}
