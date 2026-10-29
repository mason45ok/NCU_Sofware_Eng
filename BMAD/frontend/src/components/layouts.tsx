import {
  Anchor,
  AppShell,
  Burger,
  Button,
  Container,
  Group,
  Menu,
  NavLink,
  Stack,
  Text,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { Link, Outlet, useNavigate } from 'react-router-dom';
import { useLogout, useMe } from '../api/queries';

export function PublicLayout() {
  const { data: me } = useMe();
  const logout = useLogout();
  const navigate = useNavigate();
  const [opened, { toggle }] = useDisclosure(false);

  const links = (
    <>
      <Anchor component={Link} to="/spaces" c="dark">
        找空間
      </Anchor>
      {me && (
        <>
          <Anchor component={Link} to="/me/bookings" c="dark">
            我的訂單
          </Anchor>
          <Anchor component={Link} to="/me/favorites" c="dark">
            收藏
          </Anchor>
        </>
      )}
      <Anchor component={Link} to="/contact" c="dark">
        聯絡我們
      </Anchor>
    </>
  );

  return (
    <AppShell header={{ height: 60 }} padding="md" bg="#FAF6F0">
      <AppShell.Header>
        <Container size="lg" h="100%">
          <Group h="100%" justify="space-between" wrap="nowrap">
            <Group>
              <Burger
                opened={opened}
                onClick={toggle}
                hiddenFrom="sm"
                size="sm"
                aria-label="開啟選單"
              />
              <Anchor component={Link} to="/" fw={700} fz="xl" c="caramel.7" underline="never">
                聚點
              </Anchor>
              <Group gap="lg" visibleFrom="sm">
                {links}
              </Group>
            </Group>
            {me ? (
              <Menu position="bottom-end">
                <Menu.Target>
                  <Button variant="subtle" aria-label="帳號選單">
                    {me.name}
                  </Button>
                </Menu.Target>
                <Menu.Dropdown>
                  <Menu.Item component={Link} to="/me/profile">
                    個人資料
                  </Menu.Item>
                  {me.role === 'ADMIN' && (
                    <Menu.Item component={Link} to="/admin">
                      管理後台
                    </Menu.Item>
                  )}
                  <Menu.Item
                    onClick={() => logout.mutate(undefined, { onSuccess: () => navigate('/') })}
                  >
                    登出
                  </Menu.Item>
                </Menu.Dropdown>
              </Menu>
            ) : (
              <Group gap="xs">
                <Button component={Link} to="/login" variant="default" size="xs">
                  登入
                </Button>
                <Button component={Link} to="/register" size="xs">
                  註冊
                </Button>
              </Group>
            )}
          </Group>
        </Container>
        {opened && (
          <Stack p="md" hiddenFrom="sm" bg="white">
            {links}
          </Stack>
        )}
      </AppShell.Header>
      <AppShell.Main>
        <Container size="lg" py="md">
          {me && me.status !== 'ACTIVE' && (
            <Text c="red" mb="md" role="alert">
              您的帳號目前為「{me.status === 'FROZEN' ? '凍結' : '黑名單'}」狀態
              {me.status_reason ? `（${me.status_reason}）` : ''}
              ，無法新預約、付款或改期，請聯絡客服。
            </Text>
          )}
          <Outlet />
        </Container>
      </AppShell.Main>
    </AppShell>
  );
}

const ADMIN_LINKS = [
  ['/admin', '首頁'],
  ['/admin/bookings', '訂單'],
  ['/admin/branches', '場館'],
  ['/admin/spaces', '空間'],
  ['/admin/equipment', '設備'],
  ['/admin/users', '會員'],
  ['/admin/reviews', '評論'],
  ['/admin/notifications', '通知紀錄'],
] as const;

export function AdminLayout() {
  const [opened, { toggle }] = useDisclosure();
  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{ width: 200, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding="md"
      bg="#FAF6F0"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group>
            <Burger
              opened={opened}
              onClick={toggle}
              hiddenFrom="sm"
              size="sm"
              aria-label="開啟選單"
            />
            <Text fw={700} c="caramel.7">
              聚點 管理後台
            </Text>
          </Group>
          <Anchor component={Link} to="/" size="sm">
            回到前台
          </Anchor>
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="xs" aria-label="後台選單">
        {ADMIN_LINKS.map(([to, label]) => (
          <NavLink key={to} component={Link} to={to} label={label} />
        ))}
      </AppShell.Navbar>
      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
