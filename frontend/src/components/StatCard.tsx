import { Card, Group, Text, ThemeIcon } from "@mantine/core";
import { ReactNode } from "react";

export default function StatCard({ icon, label, value, color = "indigo" }: {
  icon: ReactNode;
  label: string;
  value: string | number | null | undefined;
  color?: string;
}) {
  return (
    <Card withBorder radius="md" padding="md">
      <Group justify="space-between">
        <div>
          <Text size="xs" c="dimmed" tt="uppercase" fw={600}>{label}</Text>
          <Text fw={700} size="1.6rem">{value ?? "—"}</Text>
        </div>
        <ThemeIcon color={color} variant="light" size={44} radius="md">{icon}</ThemeIcon>
      </Group>
    </Card>
  );
}
