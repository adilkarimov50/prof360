import { useEffect, useMemo, useState } from "react";
import {
  Anchor, Badge, Card, Group, Loader, Center, SegmentedControl, SimpleGrid,
  Stack, Text, Title,
} from "@mantine/core";
import { IconExternalLink, IconMapPin } from "@tabler/icons-react";
import api from "../api";
import PageHeader from "../components/PageHeader";
import ErrorState from "../components/ErrorState";
import type { LocalityOverview } from "../types/api";

const PASSPORT_SITE = "https://adilkarimov50.github.io/krim-passport";

function statusBadge(status: string | undefined) {
  if (status === "profile_only") {
    return <Badge color="blue" variant="light">Обзор</Badge>;
  }
  return <Badge color="yellow" variant="light">Полный паспорт</Badge>;
}

function fmt(n: number | null | undefined) {
  if (n == null) return "—";
  return n.toLocaleString("ru-RU");
}

export default function LocalitiesOverview() {
  const [items, setItems] = useState<LocalityOverview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    api
      .get<LocalityOverview[]>("/localities")
      .then((r) => setItems(r.data))
      .catch(() => setError("Не удалось загрузить профили населённых пунктов"))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    if (filter === "city") return items.filter((i) => i.locality_profile?.settlement_type === "city");
    if (filter === "village") return items.filter((i) => i.locality_profile?.settlement_type === "village");
    return items;
  }, [items, filter]);

  if (loading) return <Center h="60vh"><Loader /></Center>;
  if (error) return <ErrorState message={error} />;

  return (
    <Stack>
      <PageHeader
        title="Криминологические паспорта"
        subtitle="9 населённых пунктов Алматинской области и г. Алматы — профили БНС и полные кримпаспорта."
      />

      <Group justify="space-between" align="center">
        <SegmentedControl
          value={filter}
          onChange={setFilter}
          data={[
            { label: "Все", value: "all" },
            { label: "Города", value: "city" },
            { label: "Сёла", value: "village" },
          ]}
        />
        <Anchor href={PASSPORT_SITE} target="_blank" rel="noreferrer" size="sm">
          <Group gap={4}>
            <IconExternalLink size={14} />
            Публичный сайт паспортов
          </Group>
        </Anchor>
      </Group>

      <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
        {filtered.map((loc) => {
          const lp = loc.locality_profile;
          const ethnic = (lp?.ethnic_composition || [])
            .slice(0, 3)
            .map((e) => `${e.group} ${e.share_pct}%`)
            .join(", ");
          const economy = (lp?.economy?.primary_activity || []).join(", ") || "—";
          const highlight = (lp?.highlights || [])[0] || loc.summary?.description || "";

          return (
            <Card key={loc.id} withBorder radius="md" padding="lg">
              <Group justify="space-between" mb="xs">
                <Group gap="xs">
                  <IconMapPin size={16} />
                  <Title order={4}>{loc.name}</Title>
                </Group>
                {statusBadge(loc.passport_status)}
              </Group>
              <Text size="sm" c="dimmed" mb="md">{loc.district || lp?.admin_unit}</Text>
              <Text size="sm" mb="md">{highlight}</Text>
              <Stack gap={6}>
                <Group justify="space-between">
                  <Text size="sm" c="dimmed">Население</Text>
                  <Text size="sm" fw={600}>{fmt(lp?.population?.total ?? loc.summary?.population)}</Text>
                </Group>
                <Group justify="space-between">
                  <Text size="sm" c="dimmed">Этнос (топ-3)</Text>
                  <Text size="sm" ta="right" maw="55%">{ethnic || "—"}</Text>
                </Group>
                <Group justify="space-between">
                  <Text size="sm" c="dimmed">Экономика</Text>
                  <Text size="sm" ta="right" maw="55%">{economy}</Text>
                </Group>
              </Stack>
              <Anchor
                href={`${PASSPORT_SITE}/passport.html?id=${loc.id}`}
                target="_blank"
                rel="noreferrer"
                mt="md"
                size="sm"
              >
                Открыть на сайте →
              </Anchor>
            </Card>
          );
        })}
      </SimpleGrid>
    </Stack>
  );
}
