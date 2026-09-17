import { useMemo, useState } from 'react'
import { FlatList, Pressable, RefreshControl, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useQuery } from '@tanstack/react-query'
import { Ionicons } from '@expo/vector-icons'
import { fetchContacts } from '../../api/contacts'
import { isApiError } from '../../api/client'
import type { Contact } from '../../api/types'
import { AppText, Button, Center, TextField } from '../../ui'
import { colors, radius, spacing } from '../../theme'
import type { ContactsStackParams } from '../../navigation/types'

type Nav = NativeStackNavigationProp<ContactsStackParams, 'ContactsList'>

//: `none` از مهاجرتِ ۰۱۶۴ ممکن شد — واسطه/سهامدار/کارمندِ خالص. بدونِ این
//: برچسب، صفحه رشته‌ی خامِ «none» را نشان می‌داد.
const TYPE_LABEL: Record<string, string> = {
  customer: 'مشتری', supplier: 'تأمین‌کننده', both: 'مشتری/تأمین‌کننده',
  none: 'بدونِ نقشِ معاملاتی',
}

export function ContactsListScreen() {
  const nav = useNavigation<Nav>()
  const [q, setQ] = useState('')
  const query = useQuery({ queryKey: ['contacts'], queryFn: fetchContacts })

  const filtered = useMemo(() => {
    const all = query.data ?? []
    const t = q.trim()
    if (!t) return all
    return all.filter((c) => c.name.includes(t) || (c.phone ?? '').includes(t))
  }, [query.data, q])

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <AppText variant="title">اشخاص</AppText>
        <TextField
          value={q}
          onChangeText={setQ}
          placeholder="جست‌وجوی نام یا تلفن…"
          autoCapitalize="none"
        />
      </View>

      {query.isLoading ? (
        <Center>
          <AppText variant="body" color={colors.textMuted}>در حال دریافت…</AppText>
        </Center>
      ) : query.error ? (
        <Center>
          <AppText variant="body" color={colors.danger}>
            {isApiError(query.error) ? query.error.message : 'خطا در دریافتِ اشخاص'}
          </AppText>
          <Button label="تلاش دوباره" variant="ghost" onPress={query.refetch} />
        </Center>
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(c) => c.id}
          contentContainerStyle={styles.list}
          refreshControl={
            <RefreshControl refreshing={query.isFetching} onRefresh={query.refetch} tintColor={colors.accent} />
          }
          ListEmptyComponent={
            <Center>
              <AppText variant="body" color={colors.textMuted}>
                {q ? 'موردی یافت نشد.' : 'شخصی ثبت نشده است.'}
              </AppText>
            </Center>
          }
          renderItem={({ item }) => <ContactRow contact={item} onPress={() => nav.navigate('ContactDetail', { id: item.id, name: item.name })} />}
        />
      )}
    </SafeAreaView>
  )
}

function ContactRow({ contact, onPress }: { contact: Contact; onPress: () => void }) {
  const initial = contact.name.trim().charAt(0) || '؟'
  return (
    <Pressable
      onPress={onPress}
      android_ripple={{ color: colors.surfaceAlt }}
      style={({ pressed }) => [styles.row, pressed && { opacity: 0.85 }]}
    >
      <View style={styles.avatar}>
        <AppText variant="heading" color={colors.accent}>{initial}</AppText>
      </View>
      <View style={{ flex: 1 }}>
        <AppText variant="body" weight="semibold" numberOfLines={1}>{contact.name}</AppText>
        <AppText variant="caption" color={colors.textMuted}>
          {TYPE_LABEL[contact.type] ?? contact.type}
          {contact.phone ? ` · ${contact.phone}` : ''}
        </AppText>
      </View>
      <Ionicons name="chevron-back" size={18} color={colors.textFaint} />
    </Pressable>
  )
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  header: { padding: spacing.lg, gap: spacing.md },
  list: { paddingHorizontal: spacing.lg, paddingBottom: spacing.xl, gap: spacing.sm },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
  },
  avatar: {
    width: 42,
    height: 42,
    borderRadius: radius.pill,
    backgroundColor: colors.accentSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
})
