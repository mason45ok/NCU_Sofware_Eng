import { Button, NativeSelect, Pagination, Stack, Table, Text, Title } from '@mantine/core';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../../api/client';
import type { NotificationLog, Page } from '../../api/types';
import { ErrorAlert, QueryState, toast } from '../../components/common';
import { NOTIFY_TYPE, formatLocal } from '../../lib/format';

export function AdminNotificationsPage() {
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const status = params.get('status') ?? '';
  const [page, setPage] = useState(1);
  const list = useQuery({
    queryKey: ['admin-notifications', status, page],
    queryFn: () => api.get<Page<NotificationLog>>('/admin/notifications', { status, page }),
  });
  const retry = useMutation({
    mutationFn: (id: number) => api.post(`/admin/notifications/${id}/retry`),
    onSuccess: () => {
      toast('已重試寄送');
      qc.invalidateQueries({ queryKey: ['admin-notifications'] });
    },
  });
  return (
    <Stack>
      <Title order={2}>通知紀錄</Title>
      <NativeSelect
        label="狀態"
        w={200}
        value={status}
        onChange={(e) => {
          setPage(1);
          setParams(e.currentTarget.value ? { status: e.currentTarget.value } : {});
        }}
        data={[
          { value: '', label: '全部' },
          { value: 'PENDING', label: '待寄送' },
          { value: 'SENT', label: '已寄出' },
          { value: 'FAILED', label: '失敗' },
        ]}
      />
      <ErrorAlert error={retry.error} />
      <QueryState loading={list.isLoading} error={list.error}>
        <Table.ScrollContainer minWidth={720}>
          <Table striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>時間</Table.Th>
                <Table.Th>類型</Table.Th>
                <Table.Th>收件者</Table.Th>
                <Table.Th>狀態</Table.Th>
                <Table.Th>錯誤</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {list.data?.items.map((n) => (
                <Table.Tr key={n.notification_id}>
                  <Table.Td>{formatLocal(n.created_at)}</Table.Td>
                  <Table.Td>{NOTIFY_TYPE[n.type]}</Table.Td>
                  <Table.Td>{n.recipient}</Table.Td>
                  <Table.Td>
                    {n.status}（{n.attempts} 次）
                  </Table.Td>
                  <Table.Td>{n.error_message}</Table.Td>
                  <Table.Td>
                    {n.status === 'FAILED' && n.booking_id && (
                      <Button
                        size="xs"
                        variant="default"
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
        </Table.ScrollContainer>
        {list.data?.items.length === 0 && <Text c="dimmed">沒有紀錄</Text>}
        <Pagination
          total={Math.ceil((list.data?.total ?? 0) / (list.data?.page_size ?? 20))}
          value={page}
          onChange={setPage}
        />
      </QueryState>
    </Stack>
  );
}
