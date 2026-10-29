import {
  Alert,
  Button,
  Card,
  Group,
  Modal,
  NativeSelect,
  NumberInput,
  Pagination,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { api, newKey } from '../../api/client';
import type { Booking, NotificationLog, Page, StatusLog } from '../../api/types';
import { ErrorAlert, QueryState, StatusBadge, toast } from '../../components/common';
import {
  ACCESS_STATE,
  ACTION_LABEL,
  BOOKING_STATUS,
  NOTIFY_TYPE,
  formatLocal,
  formatRange,
  localIso,
  money,
} from '../../lib/format';

export function AdminBookingsPage() {
  const [params, setParams] = useSearchParams();
  const [page, setPage] = useState(1);
  const filters = Object.fromEntries(params.entries());
  const list = useQuery({
    queryKey: ['admin-bookings', filters, page],
    queryFn: () => api.get<Page<Booking>>('/admin/bookings', { ...filters, page }),
  });
  const [draft, setDraft] = useState(filters);
  const field = (k: string, label: string, type = 'text') => (
    <TextInput
      label={label}
      type={type}
      value={draft[k] ?? ''}
      onChange={(e) => setDraft({ ...draft, [k]: e.currentTarget.value })}
    />
  );
  return (
    <Stack>
      <Title order={2}>訂單查詢</Title>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setPage(1);
          setParams(Object.fromEntries(Object.entries(draft).filter(([, v]) => v)));
        }}
      >
        <Group align="end">
          {field('no', '訂單編號')}
          {field('email', '會員 email')}
          {field('from', '起', 'date')}
          {field('to', '迄', 'date')}
          <NativeSelect
            label="狀態"
            value={draft.status ?? ''}
            onChange={(e) => setDraft({ ...draft, status: e.currentTarget.value })}
            data={[
              { value: '', label: '全部' },
              ...Object.entries(BOOKING_STATUS).map(([value, v]) => ({ value, label: v.label })),
            ]}
          />
          <Button type="submit">查詢</Button>
        </Group>
      </form>
      <QueryState loading={list.isLoading} error={list.error}>
        <Table.ScrollContainer minWidth={720}>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>編號</Table.Th>
                <Table.Th>會員</Table.Th>
                <Table.Th>空間</Table.Th>
                <Table.Th>時段</Table.Th>
                <Table.Th>金額</Table.Th>
                <Table.Th>狀態</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {list.data?.items.map((b) => (
                <Table.Tr key={b.booking_id}>
                  <Table.Td>
                    <Link to={`/admin/bookings/${b.booking_id}`}>{b.booking_no}</Link>
                  </Table.Td>
                  <Table.Td>{b.user_email}</Table.Td>
                  <Table.Td>
                    {b.branch_name} {b.space_name}
                  </Table.Td>
                  <Table.Td>{formatRange(b.start_at, b.end_at)}</Table.Td>
                  <Table.Td>{money(b.total_amount)}</Table.Td>
                  <Table.Td>
                    <StatusBadge status={b.status} />
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
        {list.data?.items.length === 0 && <Text c="dimmed">沒有符合條件的訂單</Text>}
        <Pagination
          total={Math.ceil((list.data?.total ?? 0) / (list.data?.page_size ?? 20))}
          value={page}
          onChange={setPage}
        />
      </QueryState>
    </Stack>
  );
}

interface Detail {
  booking: Booking;
  logs: StatusLog[];
  notifications: NotificationLog[];
}

function useAfter(id: number) {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ['admin-booking', id] });
    qc.invalidateQueries({ queryKey: ['admin-bookings'] });
  };
}

function CancelModal({
  id,
  opened,
  onClose,
}: {
  id: number;
  opened: boolean;
  onClose: () => void;
}) {
  const after = useAfter(id);
  const [reason, setReason] = useState('');
  const cancel = useMutation({
    mutationFn: () => api.post(`/admin/bookings/${id}/cancel`, { reason }),
    onSuccess: () => {
      toast('已取消，已付款者已全額退款');
      after();
      onClose();
    },
  });
  return (
    <Modal opened={opened} onClose={onClose} title="取消訂單（場地因素，全額退款）">
      <Stack>
        <Textarea
          label="取消原因（必填）"
          value={reason}
          onChange={(e) => setReason(e.currentTarget.value)}
          maxLength={200}
          data-autofocus
        />
        <ErrorAlert error={cancel.error} />
        <Button
          color="red"
          disabled={!reason.trim()}
          loading={cancel.isPending}
          onClick={() => cancel.mutate()}
        >
          確認取消
        </Button>
      </Stack>
    </Modal>
  );
}

function RescheduleModal({
  b,
  opened,
  onClose,
}: {
  b: Booking;
  opened: boolean;
  onClose: () => void;
}) {
  const after = useAfter(b.booking_id);
  const [date, setDate] = useState('');
  const [hour, setHour] = useState<number | string>(10);
  const [reason, setReason] = useState('');
  const start = Number(hour);
  const move = useMutation({
    mutationFn: () =>
      api.post(`/admin/bookings/${b.booking_id}/reschedule`, {
        start_at: localIso(date, start),
        end_at: localIso(date, start + b.hours),
        reason,
      }),
    onSuccess: () => {
      toast('已改期');
      after();
      onClose();
    },
  });
  return (
    <Modal opened={opened} onClose={onClose} title="代為改期">
      <Stack>
        <Alert color="gray">時數須與原訂單相同（{b.hours} 小時），不涉及補付或退款。</Alert>
        <TextInput
          label="新日期"
          type="date"
          value={date}
          onChange={(e) => setDate(e.currentTarget.value)}
        />
        <NumberInput
          label={`開始時間（整點，結束為 +${b.hours} 小時）`}
          min={0}
          max={23}
          value={hour}
          onChange={setHour}
        />
        <Textarea
          label="原因（必填）"
          value={reason}
          onChange={(e) => setReason(e.currentTarget.value)}
          maxLength={200}
        />
        <ErrorAlert error={move.error} />
        <Button
          disabled={!date || !reason.trim()}
          loading={move.isPending}
          onClick={() => move.mutate()}
        >
          確認改期
        </Button>
      </Stack>
    </Modal>
  );
}

function RefundModal({ b, opened, onClose }: { b: Booking; opened: boolean; onClose: () => void }) {
  const after = useAfter(b.booking_id);
  const [amount, setAmount] = useState<number | string>('');
  const [reason, setReason] = useState('');
  const key = useRef(newKey());
  const refund = useMutation({
    mutationFn: () =>
      api.post(
        `/admin/bookings/${b.booking_id}/refunds`,
        { amount: Number(amount), reason: reason || null },
        { 'Idempotency-Key': key.current },
      ),
    onSuccess: () => {
      toast('已退款');
      key.current = newKey();
      after();
      onClose();
    },
    onError: (e) => {
      if ((e as { code?: string }).code !== 'IDEMPOTENCY_KEY_REUSED') key.current = newKey();
    },
  });
  return (
    <Modal opened={opened} onClose={onClose} title="部分退款">
      <Stack>
        <Text size="sm">目前實收 {money(b.net_paid)}，退款總額不可超過實收。</Text>
        <NumberInput
          label="退款金額"
          min={1}
          max={b.net_paid}
          value={amount}
          onChange={setAmount}
        />
        <TextInput
          label="原因（選填）"
          value={reason}
          onChange={(e) => setReason(e.currentTarget.value)}
        />
        <ErrorAlert error={refund.error} />
        <Button disabled={!amount} loading={refund.isPending} onClick={() => refund.mutate()}>
          確認退款
        </Button>
      </Stack>
    </Modal>
  );
}

export function AdminBookingDetailPage() {
  const id = Number(useParams().id);
  const after = useAfter(id);
  const detail = useQuery({
    queryKey: ['admin-booking', id],
    queryFn: () => api.get<Detail>(`/admin/bookings/${id}`),
  });
  const retry = useMutation({
    mutationFn: (nid: number) => api.post(`/admin/notifications/${nid}/retry`),
    onSuccess: () => {
      toast('已重寄');
      after();
    },
  });
  const [modal, setModal] = useState<'cancel' | 'move' | 'refund' | null>(null);
  const d = detail.data;
  const b = d?.booking;
  const active = b && (b.status === 'PENDING_PAYMENT' || b.status === 'CONFIRMED');
  return (
    <QueryState loading={detail.isLoading} error={detail.error}>
      {d && b && (
        <Stack>
          <Group justify="space-between">
            <Title order={2}>訂單 {b.booking_no}</Title>
            <StatusBadge status={b.status} />
          </Group>
          <Card withBorder>
            <Text>{b.user_email}</Text>
            <Text>
              {b.branch_name} {b.space_name}
            </Text>
            <Text>
              {formatRange(b.start_at, b.end_at)}（{b.hours} 小時，{b.attendees} 人）
            </Text>
            <Text>
              金額 {money(b.total_amount)}，實收 {money(b.net_paid)}
            </Text>
            {b.access_code && <Text>房間密碼狀態：{ACCESS_STATE[b.access_code.state]}</Text>}
            {b.cancel_reason && <Text c="red">取消原因：{b.cancel_reason}</Text>}
          </Card>
          <Group>
            {active && (
              <Button color="red" variant="outline" onClick={() => setModal('cancel')}>
                取消訂單
              </Button>
            )}
            {active && (
              <Button variant="default" onClick={() => setModal('move')}>
                代為改期
              </Button>
            )}
            {b.net_paid > 0 && (
              <Button variant="default" onClick={() => setModal('refund')}>
                部分退款
              </Button>
            )}
          </Group>
          <Title order={4}>付款與退款</Title>
          <Table>
            <Table.Tbody>
              {b.payments.map((p) => (
                <Table.Tr key={p.payment_id}>
                  <Table.Td>{formatLocal(p.created_at)}</Table.Td>
                  <Table.Td>{p.type === 'PAYMENT' ? '付款' : '退款'}</Table.Td>
                  <Table.Td>{money(p.amount)}</Table.Td>
                  <Table.Td>{p.method}</Table.Td>
                  <Table.Td>{p.status}</Table.Td>
                  <Table.Td>{p.transaction_no}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          <Title order={4}>狀態紀錄</Title>
          <Table>
            <Table.Tbody>
              {d.logs.map((l) => (
                <Table.Tr key={l.log_id}>
                  <Table.Td>{formatLocal(l.created_at)}</Table.Td>
                  <Table.Td>{ACTION_LABEL[l.action]}</Table.Td>
                  <Table.Td>
                    {l.from_status ?? '—'} → {l.to_status}
                  </Table.Td>
                  <Table.Td>{l.changed_by ? `使用者 #${l.changed_by}` : '系統'}</Table.Td>
                  <Table.Td>{l.reason}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          <Title order={4}>通知紀錄</Title>
          <Table>
            <Table.Tbody>
              {d.notifications.map((n) => (
                <Table.Tr key={n.notification_id}>
                  <Table.Td>{NOTIFY_TYPE[n.type]}</Table.Td>
                  <Table.Td>{n.recipient}</Table.Td>
                  <Table.Td>
                    {n.status}（{n.attempts} 次）
                  </Table.Td>
                  <Table.Td>
                    {n.status === 'FAILED' && (
                      <Button
                        size="xs"
                        variant="default"
                        loading={retry.isPending}
                        onClick={() => retry.mutate(n.notification_id)}
                      >
                        重試
                      </Button>
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          <CancelModal id={id} opened={modal === 'cancel'} onClose={() => setModal(null)} />
          <RescheduleModal b={b} opened={modal === 'move'} onClose={() => setModal(null)} />
          <RefundModal b={b} opened={modal === 'refund'} onClose={() => setModal(null)} />
        </Stack>
      )}
    </QueryState>
  );
}
