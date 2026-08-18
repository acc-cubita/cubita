import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { ContactsListScreen } from '../screens/contacts/ContactsListScreen'
import { ContactDetailScreen } from '../screens/contacts/ContactDetailScreen'
import { colors, font } from '../theme'
import type { ContactsStackParams } from './types'

const Stack = createNativeStackNavigator<ContactsStackParams>()

export function ContactsStack() {
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
      <Stack.Screen name="ContactsList" component={ContactsListScreen} options={{ headerShown: false }} />
      <Stack.Screen
        name="ContactDetail"
        component={ContactDetailScreen}
        options={({ route }) => ({ title: route.params.name })}
      />
    </Stack.Navigator>
  )
}
