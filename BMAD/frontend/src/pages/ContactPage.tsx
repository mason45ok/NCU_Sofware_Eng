import { Anchor, Stack, Table, Text, Title } from '@mantine/core';
import { useQueries, useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import type { Page, SpaceDetail, SpaceSummary } from '../api/types';
import { QueryState } from '../components/common';

/** 聯絡我們：客服 email 與各場館電話（取每個場館第一個空間的場館資訊）。 */
export function ContactPage() {
  const spaces = useQuery({
    queryKey: ['contact-spaces'],
    queryFn: () => api.get<Page<SpaceSummary>>('/spaces', { page_size: 50 }),
  });
  const firstOfBranch = new Map<string, number>();
  spaces.data?.items.forEach((s) => {
    if (!firstOfBranch.has(s.branch_name)) firstOfBranch.set(s.branch_name, s.space_id);
  });
  const details = useQueries({
    queries: [...firstOfBranch.values()].map((id) => ({
      queryKey: ['space', id],
      queryFn: () => api.get<SpaceDetail>(`/spaces/${id}`),
    })),
  });
  return (
    <Stack maw={560} mx="auto">
      <Title order={2}>聯絡我們</Title>
      <Text>
        客服信箱：<Anchor href="mailto:support@judian.local">support@judian.local</Anchor>
      </Text>
      <Text>服務時間以各場館營業時間為準。如需現場協助，請撥打下列場館電話。</Text>
      <QueryState loading={spaces.isLoading} error={spaces.error}>
        <Table>
          <Table.Tbody>
            {details.map(
              (d) =>
                d.data && (
                  <Table.Tr key={d.data.branch.branch_id}>
                    <Table.Td>{d.data.branch.name}</Table.Td>
                    <Table.Td>
                      <Anchor href={`tel:${d.data.branch.phone}`}>{d.data.branch.phone}</Anchor>
                    </Table.Td>
                    <Table.Td>
                      {d.data.branch.city}
                      {d.data.branch.district}
                      {d.data.branch.address}
                    </Table.Td>
                  </Table.Tr>
                ),
            )}
          </Table.Tbody>
        </Table>
      </QueryState>
    </Stack>
  );
}
