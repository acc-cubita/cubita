import { useState } from 'react'
import { FlatList, RefreshControl, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Ionicons } from '@expo/vector-icons'
import { useAuth } from '../../auth/AuthContext'
import {
  CONN_STATUS,
  ORDER_STATUS,
  confirmOrder,
  listDistributorConnections,
  listDistributorOrders,
  listRetailerConnections,
  listRetailerOrders,
  rejectOrder,
  setConnectionStatus,
} from '../../api/marketplace'
import type { MpConnection, MpOrder } from '../../api/types'
import { AppText, Badge, Button, Card, Center } from '../../ui'
import { Segmented, StatusPill } from '../../ui/controls'
import { colors, faMoney, faNum, spacing } from '../../theme'
import type { MarketStackParams } from '../../navigation/types'

type Nav = NativeStackNavigationProp<MarketStackParams, 'MarketHome'>

export function MarketHomeScreen() {
  const { me } = useAuth()
  const nav = useNavigation<Nav>()
  const qc = useQueryClient()
  const kind = me?.tenant_kind
  const isDist = kind === 'distributor'
  const isMarket = kind === 'distributor' || kind === 'retailer'
  const [tab, setTab] = useState<'connections' | 'orders'>('connections')
  const [busyId, setBusyId] = useState<string | null>(null)

  const connQ = useQuery({
    queryKey: ['mp-conns'],
    queryFn: () => (isDist ? listDistributorConnections() : listRetailerConnections()),
    enabled: isMarket,
  })
  const orderQ = useQuery({
    queryKey: ['mp-orders'],
    queryFn: () => (isDist ? listDistributorOrders() : listRetailerOrders()),
    enabled: isMarket,
  })

  async function act(id: string, fn: () => Promise<unknown>, refetch: () => void) {
    setBusyId(id)
    try {
      await fn()
      refetch()
      void qc.invalidateQueries({ queryKey: ['mp-unread'] })
    } catch {
      // خطا سمتِ سرور؛ فهرست دست‌نخورده می‌ماند
    } finally {
      setBusyId(null)
    }
  }

  if (!isMarket) {
    return (
      <SafeAreaView style={styles.safe} edges={['top']}>
        <View style={styles.header}>
          <AppText variant="title">بازار</AppText>
        </View>
        <Center>
          <Ionicons name="storefront-outline" size={48} color={colors.textFaint} />
          <AppText variant="body" color={colors.textMuted} style={{ textAlign: 'center' }}>
            ماژولِ بازارِ عمده‌فروشی برای این حساب فعال نیست.
          </AppText>
        </Center>
      </SafeAreaView>
    )
  }

  const goChat = (scope: 'connection' | 'order', id: string, title: string) =>
    nav.navigate('Chat', { scope, id, title })

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <AppText variant="title">{isDist ? 'پخشِ من' : 'بازارِ خرید'}</AppText>
        <Segmented
          value={tab}
          onChange={setTab}
          options={[
            { key: 'connections', label: 'اتصال‌ها' },
            { key: 'orders', label: 'سفارش‌ها' },
          ]}
        />
      </View>

      {tab === 'connections' ? (
        <FlatList
          data={connQ.data ?? []}
          keyExtractor={(c) => c.id}
          contentContainerStyle={styles.list}
          refreshControl={<RefreshControl refreshing={connQ.isFetching} onRefresh={connQ.refetch} tintColor={colors.accent} />}
          ListEmptyComponent={<Empty loading={connQ.isLoading} text="اتصالی وجود ندارد." />}
          renderItem={({ item }) => (
            <ConnectionCard
              conn={item}
              isDist={isDist}
              busy={busyId === item.id}
              onApprove={() => act(item.id, () => setConnectionStatus(item.id, 'approved'), connQ.refetch)}
              onReject={() => act(item.id, () => setConnectionStatus(item.id, 'rejected'), connQ.refetch)}
              onChat={() => goChat('connection', item.id, isDist ? item.retailer_name : item.distributor_name)}
            />
          )}
        />
      ) : (
        <FlatList
          data={orderQ.data ?? []}
          keyExtractor={(o) => o.id}
          contentContainerStyle={styles.list}
          refreshControl={<RefreshControl refreshing={orderQ.isFetching} onRefresh={orderQ.refetch} tintColor={colors.accent} />}
          ListEmptyComponent={<Empty loading={orderQ.isLoading} text="سفارشی وجود ندارد." />}
          renderItem={({ item }) => (
            <OrderCard
              order={item}
              isDist={isDist}
              busy={busyId === item.id}
              onConfirm={() => act(item.id, () => confirmOrder(item.id), orderQ.refetch)}
              onReject={() => act(item.id, () => rejectOrder(item.id), orderQ.refetch)}
              onChat={() => goChat('order', item.id, `سفارش #${item.order_number.toLocaleString('fa-IR')}`)}
            />
          )}
        />
      )}
    </SafeAreaView>
  )
}

function Empty({ loading, text }: { loading: boolean; text: string }) {
  return (
    <Center>
      <AppText variant="body" color={colors.textMuted}>
        {loading ? 'در حال دریافت…' : text}
      </AppText>
    </Center>
  )
}

function ChatButton({ unread, onPress }: { unread: number; onPress: () => void }) {
  return (
    <Button
      label="گفتگو"
      variant="ghost"
      onPress={onPress}
      icon={
        <View>
          <Ionicons name="chatbubble-ellipses-outline" size={18} color={colors.text} />
          <View style={{ position: 'absolute', top: -8, right: -10 }}>
            <Badge count={unread} />
          </View>
        </View>
      }
    />
  )
}

function ConnectionCard({
  conn,
  isDist,
  busy,
  onApprove,
  onReject,
  onChat,
}: {
  conn: MpConnection
  isDist: boolean
  busy: boolean
  onApprove: () => void
  onReject: () => void
  onChat: () => void
}) {
  const name = isDist ? conn.retailer_name : conn.distributor_name
  const st = CONN_STATUS[conn.status] ?? { label: conn.status, tone: 'muted' as const }
  const pending = conn.status === 'pending'
  return (
    <Card>
      <View style={styles.rowTop}>
        <AppText variant="heading" numberOfLines={1} style={{ flex: 1 }}>{name}</AppText>
        <StatusPill label={st.label} tone={st.tone} />
      </View>
      {conn.last_message_preview ? (
        <AppText variant="caption" color={colors.textMuted} numberOfLines={1} style={{ marginTop: spacing.xs }}>
          {conn.last_message_preview}
        </AppText>
      ) : null}
      <View style={styles.actions}>
        {isDist && pending ? (
          <>
            <View style={{ flex: 1 }}>
              <Button label={busy ? '…' : 'تأیید'} onPress={onApprove} disabled={busy} />
            </View>
            <View style={{ flex: 1 }}>
              <Button label="رد" variant="danger" onPress={onReject} disabled={busy} />
            </View>
          </>
        ) : conn.status === 'approved' ? (
          <View style={{ flex: 1 }}>
            <ChatButton unread={conn.unread_count} onPress={onChat} />
          </View>
        ) : null}
      </View>
    </Card>
  )
}

function OrderCard({
  order,
  isDist,
  busy,
  onConfirm,
  onReject,
  onChat,
}: {
  order: MpOrder
  isDist: boolean
  busy: boolean
  onConfirm: () => void
  onReject: () => void
  onChat: () => void
}) {
  const name = isDist ? order.retailer_name : order.distributor_name
  const st = ORDER_STATUS[order.status] ?? { label: order.status, tone: 'muted' as const }
  const pending = order.status === 'pending'
  return (
    <Card>
      <View style={styles.rowTop}>
        <View style={{ flex: 1 }}>
          <AppText variant="heading">سفارش #{order.order_number.toLocaleString('fa-IR')}</AppText>
          <AppText variant="caption" color={colors.textMuted} numberOfLines={1}>
            {name} · {faNum(order.lines.length)} قلم
          </AppText>
        </View>
        <StatusPill label={st.label} tone={st.tone} />
      </View>
      <View style={styles.rowTop}>
        <AppText variant="label" color={colors.textMuted}>مبلغِ کل</AppText>
        <AppText variant="heading" color={colors.accent}>{faMoney(order.total)}</AppText>
      </View>
      <View style={styles.actions}>
        {isDist && pending ? (
          <>
            <View style={{ flex: 1 }}>
              <Button label={busy ? '…' : 'تأیید'} onPress={onConfirm} disabled={busy} />
            </View>
            <View style={{ flex: 1 }}>
              <Button label="رد" variant="danger" onPress={onReject} disabled={busy} />
            </View>
          </>
        ) : (
          <View style={{ flex: 1 }}>
            <ChatButton unread={order.unread_count} onPress={onChat} />
          </View>
        )}
      </View>
    </Card>
  )
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  header: { padding: spacing.lg, gap: spacing.md },
  list: { paddingHorizontal: spacing.lg, paddingBottom: spacing.xl, gap: spacing.md },
  rowTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.md, marginTop: spacing.xs },
  actions: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.md },
})
