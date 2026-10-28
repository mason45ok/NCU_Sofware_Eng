import {
  Badge,
  Button,
  Group,
  Modal,
  NativeSelect,
  Pagination,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '../../api/client';
import type { Page, User } from '../../api/types';
import { ErrorAlert, QueryState, toast } from '../../components/common';
import { USER_STATUS, formatLocal } from '../../lib/format';

function StatusModal({ user, onClose }: { user: User; onClose: () => void }) {
  const qc = useQueryClient();
  const [status, setStatus] = useState(user.status === 'ACTIVE' ? 'FROZEN' : 'ACTIVE');
  const [reason, setReason] = useState('');
  const save = useMutation({
    mutationFn: () =>
      api.patch(`/admin/users/${user.user_id}/status`, { status, reason: reason || null }),
    onSuccess: () => {
      toast('已更新帳號狀態');
      qc.invalidateQueries({ queryKey: ['admin-users'] });
      onClose();
    },
  });
  return (
    <Modal opened onClose={onClose} title={`變更狀態：${user.email}`}>
      <Stack>
        <NativeSelect
          label="新狀態"
          value={status}
          onChange={(e) => setStatus(e.currentTarget.value)}
          data={Object.entries(USER_STATUS)
            .filter(([v]) => v !== user.status)
            .map(([value, label]) => ({ value, label }))}
        />
        {status !== 'ACTIVE' ? (
          <TextInput
            label="原因（必填）"
            value={reason}
            onChange={(e) => setReason(e.currentTarget.value)}
            maxLength={200}
          />
        ) : (
          <Text size="sm" c="dimmed">
            解除後會清除原因。
          </Text>
        )}
        <ErrorAlert error={save.error} />
        <Button
          disabled={status !== 'ACTIVE' && !reason.trim()}
          loading={save.isPending}
          onClick={() => save.mutate()}
        >
          確認
        </Button>
      </Stack>
    </Modal>
  );
}

export function AdminUsersPage() {
  const [page, setPage] = useState(1);
  const [draft, setDraft] = useState({ email: '', name: '', status: '' });
  const [filters, setFilters] = useState(draft);
  const [editing, setEditing] = useState<User | null>(null);
  const list = useQuery({
    queryKey: ['admin-users', filters, page],
    queryFn: () => api.get<Page<User>>('/admin/users', { ...filters, page }),
  });
  return (
    <Stack>
      <Title order={2}>會員管理</Title>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setPage(1);
          setFilters(draft);
        }}
      >
        <Group align="end">
          <TextInput
            label="Email"
            value={draft.email}
            onChange={(e) => setDraft({ ...draft, email: e.currentTarget.value })}
          />
          <TextInput
            label="姓名"
            value={draft.name}
            onChange={(e) => setDraft({ ...draft, name: e.currentTarget.value })}
          />
          <NativeSelect
            label="狀態"
            value={draft.status}
            onChange={(e) => setDraft({ ...draft, status: e.currentTarget.value })}
            data={[
              { value: '', label: '全部' },
              ...Object.entries(USER_STATUS).map(([value, label]) => ({ value, label })),
            ]}
          />
          <Button type="submit">查詢</Button>
        </Group>
      </form>
      <QueryState loading={list.isLoading} error={list.error}>
        <Table.ScrollContainer minWidth={720}>
          <Table striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Email</Table.Th>
                <Table.Th>姓名</Table.Th>
                <Table.Th>角色</Table.Th>
                <Table.Th>狀態</Table.Th>
                <Table.Th>原因</Table.Th>
                <Table.Th>最後登入</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {list.data?.items.map((u) => (
                <Table.Tr key={u.user_id}>
                  <Table.Td>
                    {u.email}
                    {!u.email_verified && (
                      <Badge ml="xs" color="yellow">
                        未驗證
                      </Badge>
                    )}
                  </Table.Td>
                  <Table.Td>{u.name}</Table.Td>
                  <Table.Td>{u.role === 'ADMIN' ? '管理員' : '會員'}</Table.Td>
                  <Table.Td>{USER_STATUS[u.status]}</Table.Td>
                  <Table.Td>{u.status_reason}</Table.Td>
                  <Table.Td>{u.last_login_at ? formatLocal(u.last_login_at) : '—'}</Table.Td>
                  <Table.Td>
                    {u.role === 'USER' && (
                      <Button size="xs" variant="default" onClick={() => setEditing(u)}>
                        變更狀態
                      </Button>
                    )}
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
      {editing && (
        <StatusModal key={editing.user_id} user={editing} onClose={() => setEditing(null)} />
      )}
    </Stack>
  );
}
