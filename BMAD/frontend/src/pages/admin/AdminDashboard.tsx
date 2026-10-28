import { Anchor, Card, SimpleGrid, Stack, Text, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '../../api/client';
import { QueryState } from '../../components/common';

interface Summary {
  today_bookings: number;
  pending_affected_bookings: number;
  failed_notifications: number;
}

export function AdminDashboardPage() {
  const summary = useQuery({
    queryKey: ['admin-summary'],
    queryFn: () => api.get<Summary>('/admin/summary'),
  });
  const s = summary.data;
  const cards =
    s &&
    ([
      ['今日訂單數', s.today_bookings, '/admin/bookings'],
      ['受停用影響的未來訂單', s.pending_affected_bookings, '/admin/bookings?status=CONFIRMED'],
      ['寄送失敗的通知', s.failed_notifications, '/admin/notifications?status=FAILED'],
    ] as const);
  return (
    <Stack>
      <Title order={2}>管理首頁</Title>
      <QueryState loading={summary.isLoading} error={summary.error}>
        <SimpleGrid cols={{ base: 1, sm: 3 }}>
          {cards?.map(([label, value, to]) => (
            <Card key={label} withBorder>
              <Text c="dimmed">{label}</Text>
              <Text fz={36} fw={700} c={value > 0 && label !== '今日訂單數' ? 'red' : undefined}>
                {value}
              </Text>
              <Anchor component={Link} to={to} size="sm">
                查看
              </Anchor>
            </Card>
          ))}
        </SimpleGrid>
      </QueryState>
    </Stack>
  );
}
