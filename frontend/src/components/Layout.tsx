import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AppShell, Group, Text, NavLink, Avatar, Menu, UnstyledButton, Box, Image, Badge, Burger } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconLogout, IconChevronDown, IconSettings, IconMoon, IconSun } from "@tabler/icons-react";
import { Outlet, useLocation, Link } from "react-router-dom";
import { useAuth } from "../auth";
import { ROLE_LABELS } from "../api";
import { navForRole } from "../lib/nav";
import { useThemeMode } from "../theme";

const SIDEBAR_BG = "#0b1f4d";

export default function Layout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [opened, { toggle }] = useDisclosure();
  const { colorScheme, toggle: toggleTheme } = useThemeMode();
  const items = navForRole(user?.role);

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={{ width: 270, breakpoint: "sm", collapsed: { mobile: !opened } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group gap="sm">
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
            <Image src="/emblem.png" h={36} w={36} fit="contain" alt="Герб" />
            <div>
              <Text fw={600} size="sm" lh={1.1}>Профилактика 360</Text>
              <Text size="xs" c="dimmed">Прокуратура Алматинской области</Text>
            </div>
          </Group>
          <Menu shadow="md" width={240} position="bottom-end">
            <Menu.Target>
              <UnstyledButton>
                <Group gap="xs">
                  <Avatar color="indigo" radius="xl" size={32}>{(user?.full_name || "?").slice(0, 1)}</Avatar>
                  <div style={{ textAlign: "right" }}>
                    <Text size="sm" fw={500} lh={1.1}>{user?.full_name}</Text>
                    <Text size="xs" c="dimmed">{ROLE_LABELS[user?.role || ""] || user?.role}</Text>
                  </div>
                  <IconChevronDown size={14} />
                </Group>
              </UnstyledButton>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Label>{user?.district ? `Район: ${user.district}` : "Доступ: вся область"}</Menu.Label>
              <Menu.Item leftSection={<IconSettings size={16} />} onClick={() => navigate("/settings")}>Настройки</Menu.Item>
              <Menu.Item leftSection={colorScheme === "dark" ? <IconSun size={16} /> : <IconMoon size={16} />} onClick={toggleTheme}>
                {colorScheme === "dark" ? "Светлая тема" : "Тёмная тема"}
              </Menu.Item>
              <Menu.Item leftSection={<IconLogout size={16} />} onClick={logout} color="red">Выйти</Menu.Item>
            </Menu.Dropdown>
          </Menu>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar style={{ backgroundColor: SIDEBAR_BG, border: "none" }} p="sm">
        <Box mb="md" ta="center" pt="xs">
          <Image src="/emblem.png" h={86} w={86} fit="contain" mx="auto" alt="Герб" />
          <Text c="white" fw={600} size="sm" mt={6}>Профилактика 360</Text>
          {user?.can_export && <Badge color="teal" variant="light" size="xs" mt={6}>Право экспорта</Badge>}
        </Box>
        {items.map((item) => {
          const active = item.end ? location.pathname === item.to : location.pathname.startsWith(item.to);
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              component={Link}
              to={item.to}
              label={item.label}
              active={active}
              leftSection={<Icon size={18} />}
              variant="filled"
              onClick={() => opened && toggle()}
              styles={{
                root: {
                  borderRadius: 8, marginBottom: 4,
                  color: active ? "#fff" : "#c5d0ec",
                  backgroundColor: active ? "rgba(255,255,255,0.16)" : "transparent",
                },
                label: { fontSize: 14, fontWeight: active ? 600 : 400 },
              }}
            />
          );
        })}
        <Box style={{ flex: 1 }} />
        <Text c="rgba(255,255,255,0.4)" size="xs" ta="center" pb="xs">МВД · ГП РК · Приказ №32</Text>
      </AppShell.Navbar>

      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
