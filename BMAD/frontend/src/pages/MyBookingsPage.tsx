import { Card, Group, Pagination, Stack, Tabs, Text, Title } from '@mantine/core';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMyBookings } from '../api/queries';
import { Empty, QueryState, StatusBadge } from '../components/common';
import { formatRange, money } from '../lib/format';

const TABS = [
  ['pending', '待付款'],
  ['upcoming', '即將到來'],
  ['completed', '已完成'],
  ['closed', '已取消／已失效'],
] as const;

function BookingList({ tab }: { tab: string }) {
  const [page, setPage] = useState(1);
  const list = useMyBookings(tab, page);
  return (
    <QueryState loading={list.isLoading} error={list.error}>
      {list.data?.items.length === 0 && <Empty text="目前沒有訂單" />}
      <Stack>
        {list.data?.items.map((b) => (
          <Card
            key={b.booking_id}
            withBorder
            component={Link}
            to={
              b.status === 'PENDING_PAYMENT'
                ? `/bookings/${b.booking_id}/pay`
                : `/me/bookings/${b.booking_id}`
            }
          >
            <Group justify="space-between">
              <Text fw={700}>
                {b.branch_name} {b.space_name}
              </Text>
              <StatusBadge status={b.status} />
            </Group>
            <Text>{formatRange(b.start_at, b.end_at)}</Text>
            <Group justify="space-between">
              <Text size="sm" c="dimmed">
                {b.booking_no}
              </Text>
              <Text fw={700}>{money(b.total_amount)}</Text>
            </Group>
          </Card>
        ))}
        <Pagination
          total={Math.ceil((list.data?.total ?? 0) / (list.data?.page_size ?? 10))}
          value={page}
          onChange={setPage}
        />
      </Stack>
    </QueryState>
  );
}

export function MyBookingsPage() {
  return (
    <Stack>
      <Title order={2}>我的訂單</Title>
      <Tabs defaultValue="upcoming" keepMounted={false}>
        <Tabs.List>
          {TABS.map(([v, l]) => (
            <Tabs.Tab key={v} value={v}>
              {l}
            </Tabs.Tab>
          ))}
        </Tabs.List>
        {TABS.map(([v]) => (
          <Tabs.Panel key={v} value={v} pt="md">
            <BookingList tab={v} />
          </Tabs.Panel>
        ))}
      </Tabs>
    </Stack>
  );
}
