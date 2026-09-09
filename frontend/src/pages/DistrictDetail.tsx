import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Anchor, Badge, Card, SimpleGrid, Stack, Table, Text, Title, Alert, Group, Button } from "@mantine/core";
import { IconArrowLeft } from "@tabler/icons-react";
import api from "../api";
import { RISK_COLORS } from "../api";
import StatCard from "../components/StatCard";
import { IconUsers, IconGavel, IconAlertTriangle, IconClipboardList, IconChartBar, IconCircleCheck } from "@tabler/icons-react";
import { PageLoader } from "../components/LoadingSkeleton";
import ErrorState from "../components/ErrorState";
import type { CommissionDocument, CommissionSummary } from "../types/api";

const REC_LABELS: Record<string, string> = {
  yes: "Включать",
  revise: "С доработкой",
  no: "Не включать",
};

const REC_COLORS: Record<string, string> = {
  yes: "green",
  revise: "yellow",
  no: "red",
};

export default function DistrictDetail() {
  const { name } = useParams();
  const [data, setData] = useState<any>(null);
  const [commission, setCommission] = useState<CommissionSummary | null>(null);
  const [commStats, setCommStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!name) return;
    setLoading(true);
    Promise.all([
      api.get(`/dashboard/district/${encodeURIComponent(name)}`).then((r) => setData(r.data)),
      api.get<CommissionSummary>("/commission/summary", { params: { district: name } }).then((r) => setCommission(r.data)).catch(() => setCommission(null)),
      api.get("/analytics/commission-stats").then((r) => setCommStats(r.data)).catch(() => setCommStats(null)),
    ])
      .catch(() => setError("Не удалось загрузить данные района"))
      .finally(() => setLoading(false));
  }, [name]);

  if (loading) return <PageLoader />;
  if (error || !data) return <ErrorState message={error || "Район не найден"} />;

  const c = data.counters || {};

  return (
    <Stack>
      <Anchor component={Link} to="/" size="sm"><IconArrowLeft size={14} style={{ verticalAlign: "middle" }} /> К дашборду</Anchor>
      <Title order={2}>Район: {data.district}</Title>
      <SimpleGrid cols={{ base: 1, sm: 3 }}>
        <StatCard icon={<IconUsers size={24} />} label="Лиц" value={c.persons} color="indigo" />
        <StatCard icon={<IconGavel size={24} />} label="Адм. дел" value={c.admin_cases} color="orange" />
        <StatCard icon={<IconAlertTriangle size={24} />} label="Высокий риск" value={c.high_risk} color="red" />
      </SimpleGrid>

      {commStats && (
        <Card withBorder padding="md">
          <Text fw={600} mb="sm">Темы МВК по профилактике (из базы)</Text>
          <SimpleGrid cols={{ base: 2, sm: 3, md: 6 }}>
            <StatCard icon={<IconChartBar size={20} />} label="Интернет-мошенничество" value={commStats.cyber_fraud} color="red" />
            <StatCard icon={<IconChartBar size={20} />} label="Вымогательство" value={commStats.extortion} color="orange" />
            <StatCard icon={<IconAlertTriangle size={20} />} label="Алкогольные правонарушения" value={commStats.alcohol_admin_cases} color="yellow" />
            <StatCard icon={<IconChartBar size={20} />} label="Нетрезвые правонарушители" value={commStats.alcohol_intoxicated_offenders} color="yellow" />
            <StatCard icon={<IconUsers size={20} />} label="Профучёт несов-х" value={commStats.juvenile_preventive_records} color="grape" />
            <StatCard icon={<IconChartBar size={20} />} label="Вейп (ст.301-1)" value={commStats.vape_violations} color="pink" />
          </SimpleGrid>
        </Card>
      )}
      <Card withBorder padding="md">
        <Text fw={600} mb="sm">Топ лиц по риску</Text>
        <Table striped highlightOnHover>
          <Table.Thead><Table.Tr><Table.Th>ФИО</Table.Th><Table.Th>Балл</Table.Th><Table.Th>Уровень</Table.Th></Table.Tr></Table.Thead>
          <Table.Tbody>
            {(data.top_persons || []).map((p: any) => (
              <Table.Tr key={p.id}>
                <Table.Td><Anchor component={Link} to={`/persons/${p.id}`}>{p.fio}</Anchor></Table.Td>
                <Table.Td>{p.risk_score}</Table.Td>
                <Table.Td><Badge color={RISK_COLORS[p.risk_level] || "gray"}>{p.risk_level}</Badge></Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Card>
      <Card withBorder padding="md">
        <Text fw={600} mb="sm">Топ статей</Text>
        <Table striped>
          <Table.Thead><Table.Tr><Table.Th>Статья</Table.Th><Table.Th>Дел</Table.Th></Table.Tr></Table.Thead>
          <Table.Tbody>
            {(data.articles || []).map((a: any) => (
              <Table.Tr key={a.article}><Table.Td>{a.article}</Table.Td><Table.Td>{a.count}</Table.Td></Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Card>

      <Card withBorder padding="md">
        <Group justify="space-between" mb="sm">
          <Text fw={600}>Документы комиссии по профилактике</Text>
          <Button component={Link} to="/commission" variant="light" size="xs">Все документы</Button>
        </Group>
        <Alert color="orange" mb="md" variant="light">
          Анализ PDF/сканов выполняется через внешний ИИ (Gemini). Загрузка и анализ фиксируются в журнале аудита.
        </Alert>
        {commission && commission.total > 0 ? (
          <>
            <SimpleGrid cols={{ base: 1, sm: 4 }} mb="md">
              <StatCard icon={<IconClipboardList size={24} />} label="Всего документов" value={commission.total} color="blue" />
              <StatCard icon={<IconChartBar size={24} />} label="Ср. качество" value={commission.avg_quality ?? "—"} color="teal" />
              <StatCard icon={<IconChartBar size={24} />} label="Ср. эффективность" value={commission.avg_effectiveness ?? "—"} color="grape" />
              <StatCard icon={<IconCircleCheck size={24} />} label="Рекомендовано включить" value={commission.include_yes} color="green" />
            </SimpleGrid>
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Документ</Table.Th>
                  <Table.Th>Период</Table.Th>
                  <Table.Th>Качество</Table.Th>
                  <Table.Th>Эффективность</Table.Th>
                  <Table.Th>Рекомендация</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {(commission.documents || []).map((d: CommissionDocument) => (
                  <Table.Tr key={d.id}>
                    <Table.Td>
                      <Anchor component={Link} to={`/commission/${d.id}`}>{d.title || d.original_filename}</Anchor>
                    </Table.Td>
                    <Table.Td>{d.period}</Table.Td>
                    <Table.Td>{d.quality_score != null ? d.quality_score.toFixed(0) : "—"}</Table.Td>
                    <Table.Td>{d.effectiveness_score != null ? d.effectiveness_score.toFixed(0) : "—"}</Table.Td>
                    <Table.Td>
                      {d.include_recommendation ? (
                        <Badge color={REC_COLORS[d.include_recommendation] || "gray"}>
                          {REC_LABELS[d.include_recommendation] || d.include_recommendation}
                        </Badge>
                      ) : "—"}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </>
        ) : (
          <Text c="dimmed">Документов комиссии по этому району пока нет.</Text>
        )}
      </Card>
    </Stack>
  );
}
