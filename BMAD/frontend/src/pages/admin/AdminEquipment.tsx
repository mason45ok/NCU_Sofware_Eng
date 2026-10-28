import { Button, Group, NativeSelect, Stack, Switch, Table, TextInput, Title } from '@mantine/core';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '../../api/client';
import type { Equipment } from '../../api/types';
import { ErrorAlert, QueryState } from '../../components/common';
import { EQUIPMENT_CATEGORY } from '../../lib/format';

export function AdminEquipmentPage() {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ['admin-equipment'] });
  const list = useQuery({
    queryKey: ['admin-equipment'],
    queryFn: () => api.get<{ items: Equipment[] }>('/admin/equipment'),
  });
  const [name, setName] = useState('');
  const [category, setCategory] = useState('AV');
  const create = useMutation({
    mutationFn: () => api.post('/admin/equipment', { name, category }),
    onSuccess: () => {
      setName('');
      refresh();
    },
  });
  const toggle = useMutation({
    mutationFn: (e: Equipment) =>
      api.patch(`/admin/equipment/${e.equipment_id}`, { is_active: !e.is_active }),
    onSuccess: refresh,
  });
  return (
    <Stack>
      <Title order={2}>設備管理</Title>
      <Group align="end">
        <TextInput label="設備名稱" value={name} onChange={(e) => setName(e.currentTarget.value)} />
        <NativeSelect
          label="分類"
          value={category}
          onChange={(e) => setCategory(e.currentTarget.value)}
          data={Object.entries(EQUIPMENT_CATEGORY).map(([value, label]) => ({ value, label }))}
        />
        <Button disabled={!name.trim()} loading={create.isPending} onClick={() => create.mutate()}>
          新增
        </Button>
      </Group>
      <ErrorAlert error={create.error ?? toggle.error} />
      <QueryState loading={list.isLoading} error={list.error}>
        <Table striped>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>名稱</Table.Th>
              <Table.Th>分類</Table.Th>
              <Table.Th>啟用</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {list.data?.items.map((e) => (
              <Table.Tr key={e.equipment_id}>
                <Table.Td>{e.name}</Table.Td>
                <Table.Td>{EQUIPMENT_CATEGORY[e.category]}</Table.Td>
                <Table.Td>
                  <Switch
                    checked={e.is_active}
                    aria-label={`${e.name} 啟用`}
                    onChange={() => toggle.mutate(e)}
                  />
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </QueryState>
    </Stack>
  );
}
