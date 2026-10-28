import {
  ActionIcon,
  Alert,
  Button,
  Checkbox,
  FileButton,
  Group,
  Image,
  Modal,
  NativeSelect,
  NumberInput,
  Stack,
  Table,
  Tabs,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../../api/client';
import type { AdminSpace, Booking, Branch, Equipment, SpaceDetail } from '../../api/types';
import { ErrorAlert, QueryState, toast } from '../../components/common';
import { SPACE_STATUS, SPACE_TYPES, formatRange, money } from '../../lib/format';

type Form = Omit<AdminSpace, 'space_id' | 'branch_name' | 'status'>;
const EMPTY: Form = {
  branch_id: 0,
  name: '',
  space_type: 'MEETING',
  capacity: 8,
  area: null,
  hourly_price: 300,
  description: '',
  rules: '',
  entry_guide: '',
};

function BasicForm({
  space,
  onSaved,
}: {
  space: AdminSpace | null;
  onSaved: (s: AdminSpace) => void;
}) {
  const qc = useQueryClient();
  const branches = useQuery({
    queryKey: ['admin-branches'],
    queryFn: () => api.get<{ items: Branch[] }>('/admin/branches'),
  });
  const [form, setForm] = useState<Form>(space ?? EMPTY);
  useEffect(() => {
    if (!space && !form.branch_id && branches.data?.items[0])
      setForm((f) => ({ ...f, branch_id: branches.data!.items[0].branch_id }));
  }, [branches.data]); // eslint-disable-line react-hooks/exhaustive-deps
  const save = useMutation({
    mutationFn: () =>
      space
        ? api.patch<AdminSpace>(`/admin/spaces/${space.space_id}`, form)
        : api.post<AdminSpace>('/admin/spaces', form),
    onSuccess: (s) => {
      toast('已儲存');
      qc.invalidateQueries({ queryKey: ['admin-spaces'] });
      qc.invalidateQueries({ queryKey: ['admin-space'] });
      onSaved(s);
    },
  });
  return (
    <Stack maw={560}>
      <NativeSelect
        label="場館"
        value={form.branch_id}
        onChange={(e) => setForm({ ...form, branch_id: Number(e.currentTarget.value) })}
        data={
          branches.data?.items.map((b) => ({ value: String(b.branch_id), label: b.name })) ?? []
        }
      />
      <TextInput
        label="名稱"
        value={form.name}
        onChange={(e) => setForm({ ...form, name: e.currentTarget.value })}
      />
      <NativeSelect
        label="類型"
        value={form.space_type}
        onChange={(e) => setForm({ ...form, space_type: e.currentTarget.value })}
        data={Object.entries(SPACE_TYPES).map(([value, label]) => ({ value, label }))}
      />
      <Group grow>
        <NumberInput
          label="容納人數"
          min={1}
          value={form.capacity}
          onChange={(v) => setForm({ ...form, capacity: Number(v) })}
        />
        <NumberInput
          label="坪數"
          min={0.1}
          decimalScale={1}
          value={form.area ?? ''}
          onChange={(v) => setForm({ ...form, area: v === '' ? null : Number(v) })}
        />
        <NumberInput
          label="時租（元）"
          min={1}
          value={form.hourly_price}
          onChange={(v) => setForm({ ...form, hourly_price: Number(v) })}
          description="調整時租不影響既有訂單"
        />
      </Group>
      <Textarea
        label="介紹"
        autosize
        minRows={2}
        value={form.description ?? ''}
        onChange={(e) => setForm({ ...form, description: e.currentTarget.value })}
      />
      <Textarea
        label="使用規定"
        autosize
        minRows={2}
        value={form.rules ?? ''}
        onChange={(e) => setForm({ ...form, rules: e.currentTarget.value })}
      />
      <Textarea
        label="進入方式與離場指引"
        autosize
        minRows={2}
        value={form.entry_guide ?? ''}
        onChange={(e) => setForm({ ...form, entry_guide: e.currentTarget.value })}
      />
      <ErrorAlert error={save.error} />
      <Button w="fit-content" loading={save.isPending} onClick={() => save.mutate()}>
        儲存
      </Button>
    </Stack>
  );
}

function StatusControl({ space }: { space: AdminSpace }) {
  const qc = useQueryClient();
  const [affected, setAffected] = useState<Booking[]>([]);
  const change = useMutation({
    mutationFn: (status: string) =>
      api.post<{ affected_bookings: Booking[] }>(`/admin/spaces/${space.space_id}/status`, {
        status,
      }),
    onSuccess: (r) => {
      setAffected(r.affected_bookings);
      qc.invalidateQueries({ queryKey: ['admin-space'] });
      qc.invalidateQueries({ queryKey: ['admin-spaces'] });
    },
  });
  return (
    <Stack>
      <NativeSelect
        label="狀態"
        w={200}
        value={space.status}
        onChange={(e) => change.mutate(e.currentTarget.value)}
        data={Object.entries(SPACE_STATUS).map(([value, label]) => ({ value, label }))}
      />
      <ErrorAlert error={change.error} />
      {affected.length > 0 && (
        <Alert color="yellow" title="以下未來訂單受影響，請逐筆處理（已付款者取消時全額退款）">
          {affected.map((b) => (
            <Text key={b.booking_id}>
              <Link to={`/admin/bookings/${b.booking_id}`}>{b.booking_no}</Link>{' '}
              {formatRange(b.start_at, b.end_at)}
            </Text>
          ))}
        </Alert>
      )}
    </Stack>
  );
}

function Photos({ spaceId, photos }: { spaceId: number; photos: SpaceDetail['photos'] }) {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ['admin-space', spaceId] });
  const upload = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData();
      fd.append('file', file);
      return api.post(`/admin/spaces/${spaceId}/photos`, fd);
    },
    onSuccess: refresh,
  });
  const reorder = useMutation({
    mutationFn: (ids: number[]) =>
      api.put(`/admin/spaces/${spaceId}/photos/order`, { photo_ids: ids }),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.del(`/admin/photos/${id}`),
    onSuccess: refresh,
  });
  const move = (index: number, delta: number) => {
    const ids = photos.map((p) => p.photo_id);
    const [item] = ids.splice(index, 1);
    ids.splice(index + delta, 0, item);
    reorder.mutate(ids);
  };
  return (
    <Stack>
      <FileButton onChange={(f) => f && upload.mutate(f)} accept="image/jpeg,image/png,image/webp">
        {(props) => (
          <Button w="fit-content" loading={upload.isPending} {...props}>
            上傳照片（jpg、png、webp，5 MB 以內）
          </Button>
        )}
      </FileButton>
      <ErrorAlert error={upload.error ?? reorder.error ?? remove.error} />
      {photos.length === 0 && <Text c="dimmed">尚無照片</Text>}
      {photos.map((p, i) => (
        <Group key={p.photo_id}>
          <Image src={p.image_url} w={120} h={80} radius="sm" alt={p.caption ?? `照片 ${i + 1}`} />
          <Text w={50}>{i === 0 ? '封面' : `#${i + 1}`}</Text>
          <ActionIcon
            variant="default"
            aria-label="上移"
            disabled={i === 0}
            onClick={() => move(i, -1)}
          >
            ↑
          </ActionIcon>
          <ActionIcon
            variant="default"
            aria-label="下移"
            disabled={i === photos.length - 1}
            onClick={() => move(i, 1)}
          >
            ↓
          </ActionIcon>
          <Button size="xs" color="red" variant="outline" onClick={() => remove.mutate(p.photo_id)}>
            刪除
          </Button>
        </Group>
      ))}
    </Stack>
  );
}

function EquipmentTab({
  spaceId,
  current,
}: {
  spaceId: number;
  current: SpaceDetail['equipment'];
}) {
  const qc = useQueryClient();
  const all = useQuery({
    queryKey: ['admin-equipment'],
    queryFn: () => api.get<{ items: Equipment[] }>('/admin/equipment'),
  });
  const [selected, setSelected] = useState<Record<number, { quantity: number; note: string }>>(
    Object.fromEntries(
      current.map((e) => [e.equipment_id, { quantity: e.quantity, note: e.note ?? '' }]),
    ),
  );
  const save = useMutation({
    mutationFn: () =>
      api.put(`/admin/spaces/${spaceId}/equipment`, {
        items: Object.entries(selected).map(([id, v]) => ({
          equipment_id: Number(id),
          quantity: v.quantity,
          note: v.note || null,
        })),
      }),
    onSuccess: () => {
      toast('已更新設備');
      qc.invalidateQueries({ queryKey: ['admin-space', spaceId] });
    },
  });
  const currentIds = new Set(current.map((e) => e.equipment_id));
  return (
    <Stack>
      <QueryState loading={all.isLoading} error={all.error}>
        {all.data?.items
          .filter((e) => e.is_active || currentIds.has(e.equipment_id))
          .map((e) => {
            const on = e.equipment_id in selected;
            return (
              <Group key={e.equipment_id}>
                <Checkbox
                  w={160}
                  label={e.name}
                  checked={on}
                  onChange={(ev) => {
                    const next = { ...selected };
                    if (ev.currentTarget.checked) next[e.equipment_id] = { quantity: 1, note: '' };
                    else delete next[e.equipment_id];
                    setSelected(next);
                  }}
                />
                {on && (
                  <NumberInput
                    aria-label={`${e.name} 數量`}
                    w={90}
                    min={1}
                    value={selected[e.equipment_id].quantity}
                    onChange={(v) =>
                      setSelected({
                        ...selected,
                        [e.equipment_id]: { ...selected[e.equipment_id], quantity: Number(v) || 1 },
                      })
                    }
                  />
                )}
                {on && (
                  <TextInput
                    aria-label={`${e.name} 規格`}
                    placeholder="規格，例：75 吋"
                    value={selected[e.equipment_id].note}
                    onChange={(ev) =>
                      setSelected({
                        ...selected,
                        [e.equipment_id]: {
                          ...selected[e.equipment_id],
                          note: ev.currentTarget.value,
                        },
                      })
                    }
                  />
                )}
              </Group>
            );
          })}
      </QueryState>
      <ErrorAlert error={save.error} />
      <Button w="fit-content" loading={save.isPending} onClick={() => save.mutate()}>
        儲存設備
      </Button>
    </Stack>
  );
}

export function AdminSpaceEditPage() {
  const id = Number(useParams().id);
  const detail = useQuery({
    queryKey: ['admin-space', id],
    queryFn: () => api.get<{ space: AdminSpace; detail: SpaceDetail }>(`/admin/spaces/${id}`),
  });
  return (
    <QueryState loading={detail.isLoading} error={detail.error}>
      {detail.data && (
        <Stack>
          <Title order={2}>編輯空間：{detail.data.space.name}</Title>
          <StatusControl space={detail.data.space} />
          <Tabs defaultValue="basic" keepMounted={false}>
            <Tabs.List>
              <Tabs.Tab value="basic">基本資料</Tabs.Tab>
              <Tabs.Tab value="photos">照片</Tabs.Tab>
              <Tabs.Tab value="equipment">設備</Tabs.Tab>
            </Tabs.List>
            <Tabs.Panel value="basic" pt="md">
              <BasicForm space={detail.data.space} onSaved={() => undefined} />
            </Tabs.Panel>
            <Tabs.Panel value="photos" pt="md">
              <Photos spaceId={id} photos={detail.data.detail.photos} />
            </Tabs.Panel>
            <Tabs.Panel value="equipment" pt="md">
              <EquipmentTab spaceId={id} current={detail.data.detail.equipment} />
            </Tabs.Panel>
          </Tabs>
        </Stack>
      )}
    </QueryState>
  );
}

export function AdminSpacesPage() {
  const navigate = useNavigate();
  const list = useQuery({
    queryKey: ['admin-spaces'],
    queryFn: () => api.get<{ items: AdminSpace[] }>('/admin/spaces'),
  });
  const [creating, setCreating] = useState(false);
  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>空間管理</Title>
        <Button onClick={() => setCreating(true)}>新增空間</Button>
      </Group>
      <QueryState loading={list.isLoading} error={list.error}>
        <Table.ScrollContainer minWidth={640}>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>場館</Table.Th>
                <Table.Th>名稱</Table.Th>
                <Table.Th>類型</Table.Th>
                <Table.Th>容量</Table.Th>
                <Table.Th>時租</Table.Th>
                <Table.Th>狀態</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {list.data?.items.map((s) => (
                <Table.Tr key={s.space_id}>
                  <Table.Td>{s.branch_name}</Table.Td>
                  <Table.Td>
                    <Link to={`/admin/spaces/${s.space_id}`}>{s.name}</Link>
                  </Table.Td>
                  <Table.Td>{SPACE_TYPES[s.space_type]}</Table.Td>
                  <Table.Td>{s.capacity}</Table.Td>
                  <Table.Td>{money(s.hourly_price)}</Table.Td>
                  <Table.Td>{SPACE_STATUS[s.status]}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      </QueryState>
      <Modal opened={creating} onClose={() => setCreating(false)} title="新增空間" size="lg">
        <BasicForm space={null} onSaved={(s) => navigate(`/admin/spaces/${s.space_id}`)} />
      </Modal>
    </Stack>
  );
}
