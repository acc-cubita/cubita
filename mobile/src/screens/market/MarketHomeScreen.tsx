import { useState } from 'react'
import { Alert, FlatList, RefreshControl, StyleSheet, View } from 'react-native'
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
  deliverOrder,
  listDistributorConnections,
  listDistributorOrders,
  listRetailerConnections,
  listRetailerOrders,
  rejectOrder,
  setConnectionStatus,
} from '../../api/marketplace'
import { isApiError } from '../../api/client'
import type { MpConnection, MpOrder } from '../../api/types'
import { canAccess } from '../../auth/access'
import { DeliverSheet } from './DeliverSheet'
import { AppText, Badge, Button, Card, Center } from '../../ui'
import { Segmented, StatusPill } from '../../ui/controls'
import { colors, faMoney, faNum, spacing } from '../../theme'
import { faDate } from '../../lib/format'
import type { MarketStackParams } from '../../navigation/types'

type Nav = NativeStackNavigationProp<MarketStackParams, 'MarketHome'>

export function MarketHomeScreen() {
  const { me } = useAuth()
  const nav = useNavigation<Nav>()
  const qc = useQueryClient()
  const kind = me?.tenant_kind
  const isDist = kind === 'distributor'
  const isMarket = kind === 'distributor' || kind === 'retailer'
  // کنش‌های بازار هرکدام مجوزِ متفاوتی می‌خواهند. تا پیش از این همه‌شان به هر
  // کسی که تبِ بازار را داشت نشان داده می‌شدند — مأمورِ حمل «تأیید» و «رد» می‌دید
  // و روی هرکدام ۴۰۳ می‌گرفت.
  const canApprove = canAccess(me, 'marketApprove')
  const canManage = canAccess(me, 'marketManage')
  const canDeliver = canAccess(me, 'marketDeliver')

  // مأمورِ حمل کارش سفارش است نه اتصال؛ روی تبِ اتصال‌ها نباید بیفتد.
  const deliveryOnly = canDeliver && !canApprove && !canManage
  const [tab, setTab] = useState<'connections' | 'orders'>('connections')
  // مشتق، نه بذرِ state: اگر `me` یک رندر دیرتر برسد، بذر با مقدارِ غلط قفل
  // می‌شد و مأمورِ حمل روی فهرستِ اتصال‌ها می‌ماند.
  const activeTab = deliveryOnly ? 'orders' : tab
  const [busyId, setBusyId] = useState<string | null>(null)
  const [deliverTarget, setDeliverTarget] = useState<MpOrder | null>(null)

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

  async function act(id: string, fn: () => Promise<unknown>, refetch: () => void, what = 'این کار') {
    setBusyId(id)
    try {
      await fn()
      refetch()
      void qc.invalidateQueries({ queryKey: ['mp-unread'] })
    } catch (e) {
      // پیش از این بی‌صدا رد می‌شد. برای تأیید/رد هم بد بود، ولی «ثبتِ تحویل»
      // یک کنشِ پولی است: کاربر می‌زند، هیچ اتفاقی نمی‌افتد، و نمی‌داند بار
      // تحویل ثبت شده یا نه.
      Alert.alert(`${what} انجام نشد`, isApiError(e) ? e.message : 'خطای نامشخص')
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
        <AppText variant="title">{deliveryOnly ? 'تحویلِ بار' : isDist ? 'پخشِ من' : 'بازارِ خرید'}</AppText>
        {deliveryOnly ? null : (
          <Segmented
            value={tab}
            onChange={setTab}
            options={[
              { key: 'connections', label: 'اتصال‌ها' },
              { key: 'orders', label: 'سفارش‌ها' },
            ]}
          />
        )}
      </View>

      {activeTab === 'connections' ? (
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
              canManage={canManage}
              busy={busyId === item.id}
              onApprove={() => act(item.id, () => setConnectionStatus(item.id, 'approved'), connQ.refetch, 'تأیید')}
              onReject={() => act(item.id, () => setConnectionStatus(item.id, 'rejected'), connQ.refetch, 'رد')}
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
              canApprove={canApprove}
              canManage={canManage}
              canDeliver={canDeliver}
              busy={busyId === item.id}
              onConfirm={() => act(item.id, () => confirmOrder(item.id), orderQ.refetch, 'تأیید')}
              onReject={() => act(item.id, () => rejectOrder(item.id), orderQ.refetch, 'رد')}
              onDeliver={() => setDeliverTarget(item)}
              onChat={() => goChat('order', item.id, `سفارش #${item.order_number.toLocaleString('fa-IR')}`)}
            />
          )}
        />
      )}

      {deliverTarget ? (
        <DeliverSheet
          order={deliverTarget}
          busy={busyId === deliverTarget.id}
          onCancel={() => setDeliverTarget(null)}
          onConfirm={(pct) => {
            const target = deliverTarget
            setDeliverTarget(null)
            void act(target.id, () => deliverOrder(target.id, pct), orderQ.refetch, 'ثبتِ تحویل')
          }}
        />
      ) : null}
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
  canManage,
  busy,
  onApprove,
  onReject,
  onChat,
}: {
  conn: MpConnection
  isDist: boolean
  canManage: boolean
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
        {isDist && pending && canManage ? (
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
  canApprove,
  canManage,
  canDeliver,
  busy,
  onConfirm,
  onReject,
  onDeliver,
  onChat,
}: {
  order: MpOrder
  isDist: boolean
  canApprove: boolean
  canManage: boolean
  canDeliver: boolean
  busy: boolean
  onConfirm: () => void
  onReject: () => void
  onDeliver: () => void
  onChat: () => void
}) {
  const name = isDist ? order.retailer_name : order.distributor_name
  const st = ORDER_STATUS[order.status] ?? { label: order.status, tone: 'muted' as const }
  // «placed» است نه «pending» — این همان اشتباهی بود که دکمه‌های تأیید/رد را
  // برای همیشه پنهان می‌کرد.
  const awaiting = order.status === 'placed'
  const deliverable = isDist && order.status === 'confirmed' && canDeliver
  const cash = Number(order.cash_amount)

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
      {cash > 0 ? (
        <View style={styles.rowTop}>
          <AppText variant="label" color={colors.textMuted}>نقدِ دریافتی</AppText>
          <AppText variant="label" color={colors.success}>{faMoney(cash)}</AppText>
        </View>
      ) : null}
      {order.status === 'delivered' && order.delivered_by_name ? (
        <AppText variant="caption" color={colors.textFaint} style={{ marginTop: spacing.xs }}>
          تحویل توسطِ «{order.delivered_by_name}»
          {order.delivered_at ? ` — ${faDate(order.delivered_at)}` : ''}
        </AppText>
      ) : null}
      <View style={styles.actions}>
        {isDist && awaiting && (canApprove || canManage) ? (
          <>
            {canApprove ? (
              <View style={{ flex: 1 }}>
                <Button label={busy ? '…' : 'تأیید'} onPress={onConfirm} disabled={busy} />
              </View>
            ) : null}
            {canManage ? (
              <View style={{ flex: 1 }}>
                <Button label="رد" variant="danger" onPress={onReject} disabled={busy} />
              </View>
            ) : null}
          </>
        ) : deliverable ? (
          <View style={{ flex: 1 }}>
            <Button
              label={busy ? '…' : 'ثبتِ تحویل'}
              onPress={onDeliver}
              disabled={busy}
              icon={<Ionicons name="cube-outline" size={18} color={colors.onAccent} />}
            />
          </View>
        ) : null}
        <View style={{ flex: 1 }}>
          <ChatButton unread={order.unread_count} onPress={onChat} />
        </View>
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
