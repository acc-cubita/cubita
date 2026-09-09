import { useMemo, useState } from 'react'
import { FlatList, Modal, Pressable, StyleSheet, View } from 'react-native'
import { useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useQuery } from '@tanstack/react-query'
import { Ionicons } from '@expo/vector-icons'
import { fetchItems } from '../api/invoices'
import type { Item } from '../api/types'
import type { HomeStackParams } from '../navigation/types'
import { AppText, Center, TextField } from '../ui'
import { BarcodeScanner } from '../scan/BarcodeScanner'
import { barcodeIndex } from '../stock/scanResolve'
import { colors, faMoney, radius, spacing } from '../theme'

// انتخابِ کالا برای ردیفِ فاکتور. با انتخاب، به فرمِ فاکتور برمی‌گردد (merge تا
// ردیف‌های ثبت‌شده و طرف‌حساب حفظ شوند).
export function ItemPickerScreen() {
  const nav = useNavigation<NativeStackNavigationProp<HomeStackParams>>()
  const [q, setQ] = useState('')
  const [scanning, setScanning] = useState(false)
  const [scanMiss, setScanMiss] = useState<string | null>(null)
  const itemsQ = useQuery({ queryKey: ['items'], queryFn: fetchItems })

  // همان ایندکسِ انبارگردانی — تطبیق محلی است، پس سرِ مشتری بدونِ آنتن هم کار می‌کند.
  const index = useMemo(() => barcodeIndex(itemsQ.data ?? []), [itemsQ.data])

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

  const onScan = (code: string) => {
    const found = index.get(code.trim())
    if (!found) {
      setScanMiss(code)
      return
    }
    setScanning(false)
    pick(found)
  }

  return (
    <View style={styles.screen}>
      <View style={styles.searchWrap}>
        <View style={{ flex: 1 }}>
          <TextField placeholder="جست‌وجوی نام، کد یا بارکد…" value={q} onChangeText={setQ} autoFocus />
        </View>
        <Pressable
          onPress={() => {
            setScanMiss(null)
            setScanning(true)
          }}
          android_ripple={{ color: colors.surfaceAlt }}
          style={styles.scanBtn}
        >
          <Ionicons name="barcode-outline" size={22} color={colors.onAccent} />
        </Pressable>
      </View>

      <Modal visible={scanning} animationType="slide" onRequestClose={() => setScanning(false)}>
        <View style={styles.scannerScreen}>
          <View style={styles.scannerBar}>
            <Pressable
              onPress={() => setScanning(false)}
              accessibilityRole="button"
              accessibilityLabel="بستنِ اسکنر"
              android_ripple={{ color: colors.surfaceAlt, borderless: true }}
              style={styles.scannerClose}
            >
              <Ionicons name="close" size={22} color={colors.text} />
            </Pressable>
            <AppText variant="heading">اسکنِ بارکد</AppText>
          </View>
          <BarcodeScanner
            onScan={onScan}
            hint={scanMiss ? `«${scanMiss}» به هیچ کالایی وصل نیست.` : undefined}
          />
        </View>
      </Modal>
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
  searchWrap: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: spacing.sm,
    padding: spacing.lg,
    paddingBottom: spacing.sm,
  },
  scanBtn: {
    width: 52,
    height: 52,
    borderRadius: radius.md,
    backgroundColor: colors.accent,
    alignItems: 'center',
    justifyContent: 'center',
  },
  scannerScreen: { flex: 1, backgroundColor: colors.bg },
  scannerBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    padding: spacing.md,
    backgroundColor: colors.surface,
  },
  scannerClose: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
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
