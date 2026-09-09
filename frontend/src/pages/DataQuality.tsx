import { useEffect, useState } from "react";
import { Card, SimpleGrid, Stack, Text } from "@mantine/core";
import api from "../api";
import PageHeader from "../components/PageHeader";
import StatCard from "../components/StatCard";
import { IconUsers, IconGavel, IconAlertTriangle, IconDatabase } from "@tabler/icons-react";
import { PageLoader } from "../components/LoadingSkeleton";
import ErrorState from "../components/ErrorState";

import type { DataQualityReport } from "../types/api";

export default function DataQuality() {
  const [report, setReport] = useState<DataQualityReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/ingest/quality")
      .then((r) => setReport(r.data))
      .catch(() => setError("Нет доступа к отчёту качества"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <PageLoader />;
  if (error || !report) return <ErrorState message={error || "Нет данных"} />;

  const p = report.persons || {};
  const ac = report.admin_cases || {};
  const prev = report.preventive || {};
  const sus = report.suspects || {};

  return (
    <Stack>
      <PageHeader title="Качество данных" subtitle="Пропуски и аномалии в Excel-данных" />
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
        <StatCard icon={<IconUsers size={24} />} label="Лиц всего" value={p.total} />
        <StatCard icon={<IconAlertTriangle size={24} />} label="Без ИИН" value={`${p.missing_iin} (${p.missing_iin_pct}%)`} color="orange" />
        <StatCard icon={<IconGavel size={24} />} label="Адм. дел" value={ac.total} />
        <StatCard icon={<IconDatabase size={24} />} label="Без меры" value={ac.missing_measure} color="red" />
      </SimpleGrid>
      <SimpleGrid cols={{ base: 1, lg: 2 }}>
        <Card withBorder padding="lg">
          <Text fw={600} mb="md">Лица</Text>
          <Text size="sm">Без района: {p.missing_district}</Text>
          <Text size="sm">Без ИИН: {p.missing_iin} ({p.missing_iin_pct}%)</Text>
        </Card>
        <Card withBorder padding="lg">
          <Text fw={600} mb="md">Административные дела</Text>
          <Text size="sm">Без даты: {ac.missing_date} ({ac.missing_date_pct}%)</Text>
          <Text size="sm">Без квалификации: {ac.missing_qualification}</Text>
          <Text size="sm">Без решения: {ac.missing_decision}</Text>
          <Text size="sm">Наложение без меры: {ac.imposed_without_measure}</Text>
        </Card>
        <Card withBorder padding="lg">
          <Text fw={600} mb="md">Профучёт</Text>
          <Text size="sm">Записей: {prev.total}</Text>
          <Text size="sm">Без даты постановки: {prev.missing_date_post}</Text>
        </Card>
        <Card withBorder padding="lg">
          <Text fw={600} mb="md">ЕРДР</Text>
          <Text size="sm">Подозреваемых: {sus.total}</Text>
          <Text size="sm">Не привязано к лицу: {sus.unlinked_to_person}</Text>
        </Card>
      </SimpleGrid>
    </Stack>
  );
}
