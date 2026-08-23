import { useMemo, useState } from 'react'
import { FlatList, Pressable, StyleSheet, View } from 'react-native'
import { useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useQuery } from '@tanstack/react-query'
import { Ionicons } from '@expo/vector-icons'
import { fetchItems } from '../api/invoices'
import type { Item } from '../api/types'
import type { HomeStackParams } from '../navigation/types'
import { AppText, Center, TextField } from '../ui'
import { colors, faMoney, radius, spacing } from '../theme'

// انتخابِ کالا برای ردیفِ فاکتور. با انتخاب، به فرمِ فاکتور برمی‌گردد (merge تا
// ردیف‌های ثبت‌شده و طرف‌حساب حفظ شوند).
export function ItemPickerScreen() {
  const nav = useNavigation<NativeStackNavigationProp<HomeStackParams>>()
  const [q, setQ] = useState('')
  const itemsQ = useQuery({ queryKey: ['items'], queryFn: fetchItems })

  const filtered = useMemo(() => {
    const all = (itemsQ.data ?? []).filter((i) => i.is_active)
    const term = q.trim()
    if (!term) return all
    return all.filter(
      (i) => i.name.includes(term) || i.sku.includes(term) || (i.barcode ?? '').includes(term),
    )
  }, [itemsQ.data, q])

  const pick = (it: Item) => {
    nav.navigate(
      'NewInvoice',
      {
        pickedItem: { id: it.id, name: it.name, unit: it.unit, sales_price: it.sales_price },
      } as never,
      { merge: true },
    )
  }

  return (
    <View style={styles.screen}>
      <View style={styles.searchWrap}>
        <TextField placeholder="جست‌وجوی نام، کد یا بارکد…" value={q} onChangeText={setQ} autoFocus />
      </View>
      {itemsQ.isLoading ? (
        <Center>
          <AppText variant="body" color={colors.textMuted}>
            در حال بارگذاری…
          </AppText>
        </Center>
      ) : filtered.length === 0 ? (
        <Center>
          <AppText variant="body" color={colors.textMuted}>
            کالایی پیدا نشد.
          </AppText>
        </Center>
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(i) => i.id}
          contentContainerStyle={styles.list}
          keyboardShouldPersistTaps="handled"
          renderItem={({ item }) => (
            <Pressable onPress={() => pick(item)} android_ripple={{ color: colors.surfaceAlt }} style={styles.row}>
              <View style={{ flex: 1 }}>
                <AppText variant="body" weight="semibold" numberOfLines={1}>
                  {item.name}
                </AppText>
                <AppText variant="caption" color={colors.textMuted}>
                  {item.sku} · {item.unit}
                </AppText>
              </View>
              <AppText variant="label" color={colors.accent}>
                {faMoney(item.sales_price)}
              </AppText>
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
