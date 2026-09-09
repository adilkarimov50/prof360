import { Group, Stack, Text, Title } from "@mantine/core";
import { ReactNode } from "react";

export default function PageHeader({ title, subtitle, actions }: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <Group justify="space-between" align="flex-start" wrap="wrap">
      <Stack gap={4}>
        <Title order={2}>{title}</Title>
        {subtitle && <Text c="dimmed" size="sm">{subtitle}</Text>}
      </Stack>
      {actions}
    </Group>
  );
}
