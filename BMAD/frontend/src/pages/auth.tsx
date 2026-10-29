import {
  Alert,
  Anchor,
  Button,
  Divider,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useMutation } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { z } from 'zod';
import { api } from '../api/client';
import { useRefreshSession } from '../api/queries';
import { ErrorAlert } from '../components/common';
import { useZodForm } from '../lib/forms';

const password = z
  .string()
  .min(8, '密碼至少 8 碼')
  .regex(/[A-Za-z]/, '密碼須包含英文')
  .regex(/\d/, '密碼須包含數字');
const email = z.string().min(1, '請輸入 email').email('email 格式不正確');

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Stack maw={420} mx="auto" mt="xl" gap="md">
      <Title order={2}>{title}</Title>
      {children}
    </Stack>
  );
}

const GOOGLE_ERRORS: Record<string, string> = {
  ACCOUNT_ALREADY_LINKED: '此 email 的帳號已綁定另一個 Google 帳號，請改用原本的 Google 帳號登入',
};

export function GoogleButton() {
  return (
    <Button component="a" href="/api/v1/auth/google/start" variant="default" fullWidth>
      使用 Google 登入
    </Button>
  );
}

export function LoginPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const refresh = useRefreshSession();
  const form = useZodForm(z.object({ email, password: z.string().min(1, '請輸入密碼') }));
  const login = useMutation({
    mutationFn: (body: { email: string; password: string }) => api.post('/auth/login', body),
    onSuccess: async () => {
      await refresh();
      navigate(params.get('next') || '/', { replace: true });
    },
  });
  const googleError = GOOGLE_ERRORS[params.get('error') ?? ''];
  return (
    <Card title="登入">
      {googleError && (
        <Alert color="red" role="alert">
          {googleError}
        </Alert>
      )}
      <form
        onSubmit={form.handleSubmit((v) => login.mutate(v as { email: string; password: string }))}
      >
        <Stack>
          <TextInput
            label="Email"
            type="email"
            autoComplete="email"
            {...form.register('email')}
            error={form.formState.errors.email?.message}
          />
          <PasswordInput
            label="密碼"
            autoComplete="current-password"
            {...form.register('password')}
            error={form.formState.errors.password?.message}
          />
          <ErrorAlert error={login.error} />
          <Button type="submit" loading={login.isPending}>
            登入
          </Button>
        </Stack>
      </form>
      <GoogleButton />
      <Divider />
      <Text size="sm">
        <Anchor component={Link} to="/forgot-password">
          忘記密碼？
        </Anchor>
        <Anchor component={Link} to="/register">
          建立新帳號
        </Anchor>
      </Text>
    </Card>
  );
}

export function RegisterPage() {
  const refresh = useRefreshSession();
  const form = useZodForm(
    z.object({ email, name: z.string().min(1, '請輸入姓名').max(50), password }),
  );
  const register = useMutation({
    mutationFn: (body: object) => api.post('/auth/register', body),
    onSuccess: refresh,
  });
  if (register.isSuccess)
    return (
      <Card title="請查收信件">
        <Alert color="olive">
          我們已寄出驗證信，請於 24 小時內點擊信中連結完成 email 驗證。驗證後即可預約空間。
        </Alert>
        <Button component={Link} to="/spaces">
          先逛逛空間
        </Button>
      </Card>
    );
  return (
    <Card title="註冊">
      <form onSubmit={form.handleSubmit((v) => register.mutate(v))}>
        <Stack>
          <TextInput
            label="Email"
            type="email"
            autoComplete="email"
            {...form.register('email')}
            error={form.formState.errors.email?.message}
          />
          <TextInput
            label="姓名"
            autoComplete="name"
            {...form.register('name')}
            error={form.formState.errors.name?.message}
          />
          <PasswordInput
            label="密碼"
            description="至少 8 碼，且須同時包含英文與數字"
            autoComplete="new-password"
            {...form.register('password')}
            error={form.formState.errors.password?.message}
          />
          <ErrorAlert error={register.error} />
          <Button type="submit" loading={register.isPending}>
            註冊
          </Button>
        </Stack>
      </form>
      <GoogleButton />
      <Text size="sm">
        已有帳號？
        <Anchor component={Link} to="/login">
          登入
        </Anchor>
      </Text>
    </Card>
  );
}

export function VerifyEmailPage() {
  const token = useSearchParams()[0].get('token') ?? '';
  const refresh = useRefreshSession();
  const fired = useRef(false);
  const verify = useMutation({
    mutationFn: () => api.post('/auth/verify-email', { token }),
    onSuccess: refresh,
  });
  useEffect(() => {
    if (!fired.current && token) {
      fired.current = true;
      verify.mutate();
    }
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps
  const form = useZodForm(z.object({ email }));
  const resend = useMutation({
    mutationFn: (b: { email: string }) => api.post('/auth/resend-verification', b),
  });
  return (
    <Card title="Email 驗證">
      {verify.isSuccess && (
        <Alert color="olive">
          驗證完成！
          <Anchor component={Link} to="/spaces">
            開始找空間
          </Anchor>
        </Alert>
      )}
      {(verify.isError || !token) && (
        <>
          <Alert color="red" role="alert">
            驗證連結無效、已過期或已使用。請輸入註冊的 email 重新寄送驗證信。
          </Alert>
          <form onSubmit={form.handleSubmit((v) => resend.mutate(v as { email: string }))}>
            <Stack>
              <TextInput
                label="Email"
                {...form.register('email')}
                error={form.formState.errors.email?.message}
              />
              <Button type="submit" loading={resend.isPending}>
                重新寄送驗證信
              </Button>
              {resend.isSuccess && (
                <Alert color="olive">若此 email 已註冊且尚未驗證，驗證信已寄出，請查收。</Alert>
              )}
            </Stack>
          </form>
        </>
      )}
    </Card>
  );
}

export function ForgotPasswordPage() {
  const form = useZodForm(z.object({ email }));
  const forgot = useMutation({
    mutationFn: (b: { email: string }) => api.post('/auth/forgot-password', b),
  });
  return (
    <Card title="忘記密碼">
      <form onSubmit={form.handleSubmit((v) => forgot.mutate(v as { email: string }))}>
        <Stack>
          <TextInput
            label="Email"
            type="email"
            {...form.register('email')}
            error={form.formState.errors.email?.message}
          />
          <ErrorAlert error={forgot.error} />
          <Button type="submit" loading={forgot.isPending}>
            寄送重設密碼信
          </Button>
          {forgot.isSuccess && (
            <Alert color="olive">
              若此 email 已註冊，重設密碼信已寄出，請於 30 分鐘內點擊信中連結。
            </Alert>
          )}
        </Stack>
      </form>
    </Card>
  );
}

function TokenPasswordPage({
  title,
  endpoint,
  done,
}: {
  title: string;
  endpoint: string;
  done: string;
}) {
  const token = useSearchParams()[0].get('token') ?? '';
  const form = useZodForm(z.object({ password }));
  const submit = useMutation({
    mutationFn: (b: { password: string }) => api.post(endpoint, { token, ...b }),
  });
  return (
    <Card title={title}>
      {submit.isSuccess ? (
        <Alert color="olive">
          {done}
          <Anchor component={Link} to="/login">
            前往登入
          </Anchor>
        </Alert>
      ) : (
        <form onSubmit={form.handleSubmit((v) => submit.mutate(v as { password: string }))}>
          <Stack>
            <PasswordInput
              label="新密碼"
              description="至少 8 碼，且須同時包含英文與數字"
              autoComplete="new-password"
              {...form.register('password')}
              error={form.formState.errors.password?.message}
            />
            <ErrorAlert error={submit.error} />
            <Button type="submit" loading={submit.isPending} disabled={!token}>
              送出
            </Button>
            {!token && <Alert color="red">連結不完整，請回到信件重新點擊連結。</Alert>}
          </Stack>
        </form>
      )}
    </Card>
  );
}

export const ResetPasswordPage = () => (
  <TokenPasswordPage title="重設密碼" endpoint="/auth/reset-password" done="密碼已重設。" />
);
export const SetPasswordPage = () => (
  <TokenPasswordPage
    title="設定密碼"
    endpoint="/auth/set-password"
    done="密碼已設定，之後可用 email 與密碼登入。"
  />
);

export function GoogleLinkPage() {
  const params = useSearchParams()[0];
  const navigate = useNavigate();
  const refresh = useRefreshSession();
  const form = useZodForm(z.object({ password: z.string().min(1, '請輸入密碼') }));
  const link = useMutation({
    mutationFn: (b: { password: string }) => api.post('/auth/google/link', b),
    onSuccess: async () => {
      await refresh();
      navigate('/', { replace: true });
    },
  });
  return (
    <Card title="確認綁定 Google 帳號">
      <Text>
        {params.get('email') ?? '此 email'}{' '}
        已有聚點帳號。為確保是您本人，請輸入該帳號的密碼，完成後即可用 Google 登入。
      </Text>
      <form onSubmit={form.handleSubmit((v) => link.mutate(v as { password: string }))}>
        <Stack>
          <PasswordInput
            label="聚點帳號密碼"
            {...form.register('password')}
            error={form.formState.errors.password?.message}
          />
          <ErrorAlert error={link.error} />
          <Button type="submit" loading={link.isPending}>
            綁定並登入
          </Button>
        </Stack>
      </form>
    </Card>
  );
}
