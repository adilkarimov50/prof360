import { Center, Loader, Skeleton, Stack } from "@mantine/core";

export function PageLoader() {
  return (
    <Center h="50vh">
      <Loader />
    </Center>
  );
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <Stack gap="xs">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} height={36} radius="sm" />
      ))}
    </Stack>
  );
}
