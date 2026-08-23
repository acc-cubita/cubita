import { useMemo, useState } from 'react'
import { FlatList, Pressable, StyleSheet, View } from 'react-native'
import { useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useQuery } from '@tanstack/react-query'
import { Ionicons } from '@expo/vector-icons'
import { fetchContacts } from '../api/contacts'
import type { Contact } from '../api/types'
import type { HomeStackParams } from '../navigation/types'
import { AppText, Center, TextField } from '../ui'
import { colors, radius, spacing } from '../theme'

// انتخابِ طرف‌حساب برای فرمِ خزانه. با انتخاب، به صفحه‌ی خزانه برمی‌گردد و طرف‌حساب را
// به‌عنوانِ param پاس می‌دهد (merge تا نوعِ تراکنش حفظ شود).
export function ContactPickerScreen() {
  const nav = useNavigation<NativeStackNavigationProp<HomeStackParams>>()
  const [q, setQ] = useState('')
  const contactsQ = useQuery({ queryKey: ['contacts'], queryFn: fetchContacts })

  const filtered = useMemo(() => {
    const all = contactsQ.data ?? []
    const term = q.trim()
    if (!term) return all
    return all.filter((c) => c.name.includes(term) || (c.phone ?? '').includes(term))
  }, [contactsQ.data, q])

  const pick = (c: Contact) => {
    // merge: نوعِ تراکنش (receipt/payment) که از قبل روی صفحه‌ی خزانه ست شده حفظ می‌شود
    // و فقط طرف‌حساب اضافه می‌گردد.
    nav.navigate(
      'Treasury',
      { pickedContact: { id: c.id, name: c.name } } as never,
      { merge: true },
    )
  }

  return (
    <View style={styles.screen}>
      <View style={styles.searchWrap}>
        <TextField placeholder="جست‌وجوی نام یا شماره…" value={q} onChangeText={setQ} autoFocus />
      </View>
      {contactsQ.isLoading ? (
        <Center>
          <AppText variant="body" color={colors.textMuted}>
            در حال بارگذاری…
          </AppText>
        </Center>
      ) : filtered.length === 0 ? (
        <Center>
          <AppText variant="body" color={colors.textMuted}>
            طرف‌حسابی پیدا نشد.
          </AppText>
        </Center>
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(c) => c.id}
          contentContainerStyle={styles.list}
          keyboardShouldPersistTaps="handled"
          renderItem={({ item }) => (
            <Pressable onPress={() => pick(item)} android_ripple={{ color: colors.surfaceAlt }} style={styles.row}>
              <View style={{ flex: 1 }}>
                <AppText variant="body" weight="semibold" numberOfLines={1}>
                  {item.name}
                </AppText>
                {item.phone ? (
                  <AppText variant="caption" color={colors.textMuted}>
                    {item.phone}
                  </AppText>
                ) : null}
              </View>
              <Ionicons name="chevron-back" size={18} color={colors.textFaint} />
            </Pressable>
          )}
          ItemSeparatorComponent={() => <View style={styles.sep} />}
        />
      )}
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  searchWrap: { padding: spacing.lg, paddingBottom: spacing.sm },
  list: { paddingHorizontal: spacing.lg, paddingBottom: spacing.xl },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
  },
  sep: { height: spacing.sm },
})
