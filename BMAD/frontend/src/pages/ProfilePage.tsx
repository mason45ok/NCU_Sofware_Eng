import { Alert, Button, Card, PasswordInput, Stack, Text, TextInput, Title } from '@mantine/core';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { api } from '../api/client';
import { useMe } from '../api/queries';
import { ErrorAlert, QueryState, toast } from '../components/common';
import { useZodForm } from '../lib/forms';

const password = z
  .string()
  .min(8, '密碼至少 8 碼')
  .regex(/[A-Za-z]/, '須包含英文')
  .regex(/\d/, '須包含數字');

function ProfileForm({ name, phone }: { name: string; phone: string | null }) {
  const qc = useQueryClient();
  const form = useZodForm(
    z.object({
      name: z.string().min(1, '請輸入姓名').max(50),
      phone: z.string().max(20).optional(),
    }),
    { name, phone: phone ?? '' },
  );
  const save = useMutation({
    mutationFn: (v: object) => api.patch('/me', v),
    onSuccess: () => {
      toast('已儲存');
      qc.invalidateQueries({ queryKey: ['me'] });
    },
  });
  return (
    <Card withBorder>
      <form onSubmit={form.handleSubmit((v) => save.mutate(v))}>
        <Stack>
          <Title order={4}>基本資料</Title>
          <TextInput
            label="姓名"
            {...form.register('name')}
            error={form.formState.errors.name?.message}
          />
          <TextInput
            label="手機"
            {...form.register('phone')}
            error={form.formState.errors.phone?.message}
          />
          <ErrorAlert error={save.error} />
          <Button type="submit" w="fit-content" loading={save.isPending}>
            儲存
          </Button>
        </Stack>
      </form>
    </Card>
  );
}

function ChangePassword() {
  const form = useZodForm(
    z.object({ old_password: z.string().min(1, '請輸入舊密碼'), new_password: password }),
  );
  const change = useMutation({
    mutationFn: (v: object) => api.put('/me/password', v),
    onSuccess: () => {
      toast('密碼已變更');
      form.reset();
    },
  });
  return (
    <Card withBorder>
      <form onSubmit={form.handleSubmit((v) => change.mutate(v))}>
        <Stack>
          <Title order={4}>變更密碼</Title>
          <PasswordInput
            label="舊密碼"
            autoComplete="current-password"
            {...form.register('old_password')}
            error={form.formState.errors.old_password?.message}
          />
          <PasswordInput
            label="新密碼"
            description="至少 8 碼，且須同時包含英文與數字"
            autoComplete="new-password"
            {...form.register('new_password')}
            error={form.formState.errors.new_password?.message}
          />
          <ErrorAlert error={change.error} />
          <Button type="submit" w="fit-content" loading={change.isPending}>
            變更密碼
          </Button>
        </Stack>
      </form>
    </Card>
  );
}

function SetPasswordCard() {
  const send = useMutation({ mutationFn: () => api.post('/me/password/setup-email') });
  return (
    <Card withBorder>
      <Stack>
        <Title order={4}>設定密碼</Title>
        <Text size="sm">您目前只使用 Google 登入。設定密碼後，也可以用 email 與密碼登入。</Text>
        <ErrorAlert error={send.error} />
        {send.isSuccess && (
          <Alert color="olive">設定密碼信已寄出，請於 30 分鐘內點擊信中連結。</Alert>
        )}
        <Button w="fit-content" loading={send.isPending} onClick={() => send.mutate()}>
          寄送設定密碼信
        </Button>
      </Stack>
    </Card>
  );
}

export function ProfilePage() {
  const { data: me, isLoading, error } = useMe();
  return (
    <QueryState loading={isLoading} error={error}>
      {me && (
        <Stack maw={520} mx="auto">
          <Title order={2}>個人資料</Title>
          <Text>
            Email：{me.email}（不可修改）{me.email_verified ? '' : ' · 尚未驗證'}
          </Text>
          <ProfileForm name={me.name} phone={me.phone} />
          {me.has_password ? <ChangePassword /> : <SetPasswordCard />}
        </Stack>
      )}
    </QueryState>
  );
}
