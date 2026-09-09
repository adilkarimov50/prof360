import { Stack, Text, ThemeIcon } from "@mantine/core";
import { IconInbox } from "@tabler/icons-react";

export default function EmptyState({ message = "Нет данных" }: { message?: string }) {
  return (
    <Stack align="center" py="xl" gap="xs">
      <ThemeIcon size={48} radius="xl" variant="light" color="gray">
        <IconInbox size={24} />
      </ThemeIcon>
      <Text c="dimmed">{message}</Text>
    </Stack>
  );
}
