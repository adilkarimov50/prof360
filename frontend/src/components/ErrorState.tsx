import { Alert, Button, Stack } from "@mantine/core";
import { IconAlertCircle } from "@tabler/icons-react";

export default function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <Stack align="center" py="xl">
      <Alert color="red" icon={<IconAlertCircle size={16} />} title="Ошибка загрузки" maw={480}>
        {message}
      </Alert>
      {onRetry && <Button variant="light" onClick={onRetry}>Повторить</Button>}
    </Stack>
  );
}
