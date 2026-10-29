import {
  Alert,
  Button,
  Group,
  Modal,
  NumberInput,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../api/client';
import type { Booking, Branch } from '../../api/types';
import { ErrorAlert, QueryState, toast } from '../../components/common';
import { formatRange } from '../../lib/format';

type Form = Omit<Branch, 'branch_id' | 'status' | 'space_count'>;
const EMPTY: Form = {
  name: '',
  city: '',
  district: '',
  address: '',
  phone: '',
  latitude: 24.9677,
  longitude: 121.1916,
  open_hour: 9,
  close_hour: 22,
};

function BranchModal({
  branch,
  opened,
  onClose,
}: {
  branch: Branch | null;
  opened: boolean;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [form, setForm] = useState<Form>(branch ?? EMPTY);
  const save = useMutation({
    mutationFn: () =>
      branch
        ? api.patch(`/admin/branches/${branch.branch_id}`, form)
        : api.post('/admin/branches', form),
    onSuccess: () => {
      toast('已儲存');
      qc.invalidateQueries({ queryKey: ['admin-branches'] });
      onClose();
    },
  });
  const text = (k: keyof Form, label: string) => (
    <TextInput
      label={label}
      value={String(form[k])}
      onChange={(e) => setForm({ ...form, [k]: e.currentTarget.value })}
    />
  );
  const num = (k: keyof Form, label: string, min?: number, max?: number, decimals = 0) => (
    <NumberInput
      label={label}
      min={min}
      max={max}
      decimalScale={decimals}
      value={form[k] as number}
      onChange={(v) => setForm({ ...form, [k]: Number(v) })}
    />
  );
  return (
    <Modal opened={opened} onClose={onClose} title={branch ? '編輯場館' : '新增場館'}>
      <Stack>
        {text('name', '名稱')}
        <Group grow>
          {text('city', '縣市')}
          {text('district', '行政區')}
        </Group>
        {text('address', '地址')}
        {text('phone', '支援電話')}
        <Group grow>
          {num('latitude', '緯度', -90, 90, 6)}
          {num('longitude', '經度', -180, 180, 6)}
        </Group>
        <Group grow>
          {num('open_hour', '開始營業（整點）', 0, 23)}
          {num('close_hour', '結束營業（整點）', 1, 23)}
        </Group>
        <ErrorAlert error={save.error} />
        <Button loading={save.isPending} onClick={() => save.mutate()}>
          儲存
        </Button>
      </Stack>
    </Modal>
  );
}

export function AdminBranchesPage() {
  const qc = useQueryClient();
  const list = useQuery({
    queryKey: ['admin-branches'],
    queryFn: () => api.get<{ items: Branch[] }>('/admin/branches'),
  });
  const [editing, setEditing] = useState<Branch | null | 'new'>(null);
  const [affected, setAffected] = useState<Booking[]>([]);
  const toggle = useMutation({
    mutationFn: (b: Branch) =>
      api.post<{ affected_bookings: Booking[] }>(`/admin/branches/${b.branch_id}/status`, {
        status: b.status === 'OPEN' ? 'DISABLED' : 'OPEN',
      }),
    onSuccess: (r) => {
      setAffected(r.affected_bookings);
      qc.invalidateQueries({ queryKey: ['admin-branches'] });
    },
  });
  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>場館管理</Title>
        <Button onClick={() => setEditing('new')}>新增場館</Button>
      </Group>
      {affected.length > 0 && (
        <Alert
          color="yellow"
          title="以下未來訂單受影響，請逐筆處理"
          withCloseButton
          onClose={() => setAffected([])}
        >
          {affected.map((b) => (
            <Text key={b.booking_id}>
              <Link to={`/admin/bookings/${b.booking_id}`}>{b.booking_no}</Link> {b.space_name}{' '}
              {formatRange(b.start_at, b.end_at)}
            </Text>
          ))}
        </Alert>
      )}
      <ErrorAlert error={toggle.error} />
      <QueryState loading={list.isLoading} error={list.error}>
        <Table.ScrollContainer minWidth={640}>
          <Table striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>名稱</Table.Th>
                <Table.Th>地區</Table.Th>
                <Table.Th>營業時間</Table.Th>
                <Table.Th>空間數</Table.Th>
                <Table.Th>狀態</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {list.data?.items.map((b) => (
                <Table.Tr key={b.branch_id}>
                  <Table.Td>{b.name}</Table.Td>
                  <Table.Td>
                    {b.city}
                    {b.district}
                  </Table.Td>
                  <Table.Td>
                    {b.open_hour}:00–{b.close_hour}:00
                  </Table.Td>
                  <Table.Td>{b.space_count}</Table.Td>
                  <Table.Td>{b.status === 'OPEN' ? '營業中' : '已停用'}</Table.Td>
                  <Table.Td>
                    <Group gap="xs">
                      <Button size="xs" variant="default" onClick={() => setEditing(b)}>
                        編輯
                      </Button>
                      <Button
                        size="xs"
                        variant="outline"
                        color={b.status === 'OPEN' ? 'red' : 'olive'}
                        loading={toggle.isPending}
                        onClick={() => toggle.mutate(b)}
                      >
                        {b.status === 'OPEN' ? '停用' : '啟用'}
                      </Button>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      </QueryState>
      {editing && (
        <BranchModal
          key={editing === 'new' ? 'new' : editing.branch_id}
          branch={editing === 'new' ? null : editing}
          opened
          onClose={() => setEditing(null)}
        />
      )}
    </Stack>
  );
}
