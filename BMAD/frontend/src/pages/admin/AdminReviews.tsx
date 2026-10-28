import { Badge, Button, Pagination, Stack, Table, Title } from '@mantine/core';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '../../api/client';
import type { Page, Review } from '../../api/types';
import { ErrorAlert, QueryState } from '../../components/common';
import { formatLocal } from '../../lib/format';

export function AdminReviewsPage() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const list = useQuery({
    queryKey: ['admin-reviews', page],
    queryFn: () => api.get<Page<Review>>('/admin/reviews', { page }),
  });
  const hide = useMutation({
    mutationFn: (r: Review) =>
      api.patch(`/admin/reviews/${r.review_id}`, { is_hidden: !r.is_hidden }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-reviews'] }),
  });
  return (
    <Stack>
      <Title order={2}>評論管理</Title>
      <ErrorAlert error={hide.error} />
      <QueryState loading={list.isLoading} error={list.error}>
        <Table.ScrollContainer minWidth={640}>
          <Table striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>空間</Table.Th>
                <Table.Th>評論者</Table.Th>
                <Table.Th>評分</Table.Th>
                <Table.Th>內容</Table.Th>
                <Table.Th>時間</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {list.data?.items.map((r) => (
                <Table.Tr key={r.review_id}>
                  <Table.Td>{r.space_name}</Table.Td>
                  <Table.Td>{r.reviewer}</Table.Td>
                  <Table.Td>{r.rating} ★</Table.Td>
                  <Table.Td>
                    {r.comment} {r.is_hidden && <Badge color="gray">已隱藏</Badge>}
                  </Table.Td>
                  <Table.Td>{formatLocal(r.created_at)}</Table.Td>
                  <Table.Td>
                    <Button
                      size="xs"
                      variant="default"
                      loading={hide.isPending}
                      onClick={() => hide.mutate(r)}
                    >
                      {r.is_hidden ? '取消隱藏' : '隱藏'}
                    </Button>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
        <Pagination
          total={Math.ceil((list.data?.total ?? 0) / (list.data?.page_size ?? 20))}
          value={page}
          onChange={setPage}
        />
      </QueryState>
    </Stack>
  );
}
