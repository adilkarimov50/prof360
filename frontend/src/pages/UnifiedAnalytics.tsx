import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Anchor,
  Badge,
  Card,
  Group,
  Progress,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
  Title,
} from "@mantine/core";
import {
  IconAlertTriangle,
  IconArrowsSplit,
  IconChartBar,
  IconGavel,
  IconMap,
  IconScale,
  IconShieldCheck,
  IconUsers,
} from "@tabler/icons-react";
import { Link } from "react-router-dom";
import api from "../api";
import PageHeader from "../components/PageHeader";
import StatCard from "../components/StatCard";
import { PageLoader } from "../components/LoadingSkeleton";
import ErrorState from "../components/ErrorState";

type PipelineStep = { key: string; label: string; count: number; pct_of_prev: number | null };
type DistrictMatrixRow = {
  district: string;
  risk_total: number;
  risk_high: number;
  risk_critical: number;
  admin_cases: number;
  preventive: number;
  signals_total: number;
  cyber_fraud: number;
  extortion: number;
  juvenile: number;
  alcohol: number;
  vape: number;
  mvk_effectiveness: number | null;
};
type LawNorm = {
  law: string;
  article: string;
  requirement: string;
  numerator: number;
  denominator: number;
  compliance_pct: number | null;
  verdict: string;
  inverted?: boolean;
  by_district?: { district: string; count: number }[];
};
type CrosscheckTopic = {
  topic: string;
  label: string;
  articles: string;
  total_stat: number;
  assignments_count: number;
  has_oblast_assignment: boolean;
  districts: { district: string; stat_count: number; mvk_covered: boolean; status: string }[];
  worst_district: string | null;
  worst_count: number;
};

function quartileColor(value: number, values: number[], invert = false): string {
  const sorted = [...values].filter((v) => v > 0).sort((a, b) => a - b);
  if (!sorted.length || value <= 0) return "gray";
  const q1 = sorted[Math.floor(sorted.length * 0.25)] ?? sorted[0];
  const q3 = sorted[Math.floor(sorted.length * 0.75)] ?? sorted[sorted.length - 1];
  if (invert) {
    if (value <= q1) return "teal";
    if (value <= q3) return "yellow";
    return "red";
  }
  if (value >= q3) return "red";
  if (value >= q1) return "yellow";
  return "teal";
}

function CellBadge({ value, all, invert }: { value: number; all: number[]; invert?: boolean }) {
  const color = quartileColor(value, all, invert);
  return <Badge color={color} variant="light">{value}</Badge>;
}

function FunnelStep({ step, maxCount }: { step: PipelineStep; maxCount: number }) {
  const width = maxCount > 0 ? Math.max(12, (step.count / maxCount) * 100) : 12;
  return (
    <Card withBorder padding="sm" radius="md">
      <Group justify="space-between" mb={6}>
        <Text size="sm" fw={600}>{step.label}</Text>
        <Group gap="xs">
          <Text fw={700}>{step.count.toLocaleString("ru-RU")}</Text>
          {step.pct_of_prev != null && (
            <Badge size="sm" variant="outline">{step.pct_of_prev}%</Badge>
          )}
        </Group>
      </Group>
      <Progress value={width} color="indigo" size="lg" radius="md" />
    </Card>
  );
}

export default function UnifiedAnalytics() {
  const [pipeline, setPipeline] = useState<any>(null);
  const [unified, setUnified] = useState<any>(null);
  const [law, setLaw] = useState<any>(null);
  const [crosscheck, setCrosscheck] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api.get("/analytics/prevention-pipeline"),
      api.get("/analytics/unified"),
      api.get("/analytics/law-compliance"),
      api.get("/analytics/commission-crosscheck"),
    ])
      .then(([p, u, l, c]) => {
        setPipeline(p.data);
        setUnified(u.data);
        setLaw(l.data);
        setCrosscheck(c.data);
        setError("");
      })
      .catch(() => setError("Не удалось загрузить сводную аналитику"))
      .finally(() => setLoading(false));
  }, []);

  const matrix: DistrictMatrixRow[] = unified?.district_matrix ?? [];
  const matrixCols = useMemo(() => ({
    admin: matrix.map((r) => r.admin_cases),
    preventive: matrix.map((r) => r.preventive),
    signals: matrix.map((r) => r.signals_total),
    cyber: matrix.map((r) => r.cyber_fraud),
    extortion: matrix.map((r) => r.extortion),
    juvenile: matrix.map((r) => r.juvenile),
    mvk: matrix.map((r) => r.mvk_effectiveness ?? 0),
  }), [matrix]);

  const funnelSteps: PipelineStep[] = pipeline?.steps ?? [];
  const maxFunnel = funnelSteps[0]?.count ?? 1;

  if (loading) return <PageLoader />;
  if (error && !pipeline) return <ErrorState message={error} />;

  return (
    <Stack gap="md">
      <PageHeader
        title="Сводная картина области"
        subtitle="Единый дашборд: адм. практика, профучёт, МВК, законодательный комплаенс и взаимосвязи"
      />

      <Alert color="blue" title="Методология">
        Данные объединяют административную практику (КоАП), профилактический учёт (Закон №245-VIII),
        уголовную статистику (УК), работу МВК и автоматические сигналы риска.
      </Alert>

      <Tabs defaultValue="funnel">
        <Tabs.List mb="md">
          <Tabs.Tab value="funnel" leftSection={<IconArrowsSplit size={16} />}>Воронка профилактики</Tabs.Tab>
          <Tabs.Tab value="matrix" leftSection={<IconMap size={16} />}>Районная матрица</Tabs.Tab>
          <Tabs.Tab value="crosscheck" leftSection={<IconChartBar size={16} />}>МВК vs реальность</Tabs.Tab>
          <Tabs.Tab value="law" leftSection={<IconScale size={16} />}>Законодательный комплаенс</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="funnel">
          <Stack gap="md">
            <SimpleGrid cols={{ base: 2, sm: 3, md: 4 }}>
              <StatCard
                icon={<IconGavel size={24} />}
                label="Конверсия в учёт (ст.73 → профучёт)"
                value={pipeline?.summary?.conversion_to_register_pct != null ? `${pipeline.summary.conversion_to_register_pct}%` : "—"}
                color="teal"
              />
              <StatCard
                icon={<IconAlertTriangle size={24} />}
                label="Пропущено постановки на учёт"
                value={pipeline?.summary?.missed_registration_pct != null ? `${pipeline.summary.missed_registration_pct}%` : "—"}
                color="red"
              />
              <StatCard
                icon={<IconUsers size={24} />}
                label="Эскалация в период учёта"
                value={pipeline?.summary?.escalation_rate_pct != null ? `${pipeline.summary.escalation_rate_pct}%` : "—"}
                color="orange"
              />
              <StatCard
                icon={<IconShieldCheck size={24} />}
                label="Подозреваемые (ЕРДР)"
                value={funnelSteps.find((s) => s.key === "suspects")?.count ?? "—"}
                color="grape"
              />
            </SimpleGrid>

            <Card withBorder padding="lg">
              <Title order={5} mb="md">Сквозная воронка профилактики</Title>
              <Stack gap="xs">
                {funnelSteps.map((step) => (
                  <FunnelStep key={step.key} step={step} maxCount={maxFunnel} />
                ))}
              </Stack>
            </Card>
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="matrix">
          <Card withBorder padding="md">
            <Text size="sm" c="dimmed" mb="md">
              Цвет ячеек: зелёный — ниже среднего, жёлтый — средний уровень, красный — повышенный риск.
              Клик по району — детализация.
            </Text>
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Район</Table.Th>
                  <Table.Th>Адм. дела</Table.Th>
                  <Table.Th>Профучёт</Table.Th>
                  <Table.Th>Сигналы</Table.Th>
                  <Table.Th>Кибер</Table.Th>
                  <Table.Th>Вымогат.</Table.Th>
                  <Table.Th>Несоверш.</Table.Th>
                  <Table.Th>Эффект. МВК</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {matrix.map((row) => (
                  <Table.Tr key={row.district}>
                    <Table.Td>
                      <Anchor component={Link} to={`/district/${encodeURIComponent(row.district)}`} fw={600}>
                        {row.district}
                      </Anchor>
                      {(row.risk_high > 0 || row.risk_critical > 0) && (
                        <Text size="xs" c="dimmed">
                          риск: {row.risk_high} выс. / {row.risk_critical} крит.
                        </Text>
                      )}
                    </Table.Td>
                    <Table.Td><CellBadge value={row.admin_cases} all={matrixCols.admin} /></Table.Td>
                    <Table.Td><CellBadge value={row.preventive} all={matrixCols.preventive} /></Table.Td>
                    <Table.Td><CellBadge value={row.signals_total} all={matrixCols.signals} /></Table.Td>
                    <Table.Td><CellBadge value={row.cyber_fraud} all={matrixCols.cyber} /></Table.Td>
                    <Table.Td><CellBadge value={row.extortion} all={matrixCols.extortion} /></Table.Td>
                    <Table.Td><CellBadge value={row.juvenile} all={matrixCols.juvenile} /></Table.Td>
                    <Table.Td>
                      {row.mvk_effectiveness != null ? (
                        <CellBadge value={row.mvk_effectiveness} all={matrixCols.mvk} invert />
                      ) : (
                        <Badge color="gray" variant="light">—</Badge>
                      )}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Card>
        </Tabs.Panel>

        <Tabs.Panel value="crosscheck">
          <Stack gap="md">
            {crosscheck?.summary && (
              <SimpleGrid cols={{ base: 1, sm: 2, md: 4 }}>
                <StatCard
                  icon={<IconChartBar size={24} />}
                  label="Охват проблемных районов МВК"
                  value={crosscheck.summary.coverage_rate_pct != null ? `${crosscheck.summary.coverage_rate_pct}%` : "—"}
                  color="indigo"
                />
                <StatCard
                  icon={<IconShieldCheck size={24} />}
                  label="Совпадения (район + тема)"
                  value={crosscheck.summary.matched_district_topics ?? "—"}
                  color="teal"
                />
                <StatCard
                  icon={<IconAlertTriangle size={24} />}
                  label="Пропущено (слепые пятна)"
                  value={crosscheck.summary.missed_district_topics ?? "—"}
                  color="orange"
                />
                <StatCard
                  icon={<IconAlertTriangle size={24} />}
                  label="Тревожные сигналы"
                  value={crosscheck.summary.alarm_count ?? "—"}
                  color="red"
                />
              </SimpleGrid>
            )}

            {crosscheck?.summary?.verdict && (
              <Alert color={crosscheck.summary.alarm_count > 0 ? "orange" : "teal"} title="Заключение">
                {crosscheck.summary.verdict}
              </Alert>
            )}

            {(crosscheck?.alarms ?? []).length > 0 && (
              <Card withBorder padding="md">
                <Title order={5} mb="sm">Слепые пятна (высокая проблема без поручения МВК)</Title>
                <Stack gap="xs">
                  {crosscheck.alarms.map((a: any, i: number) => (
                    <Alert key={i} color="red" variant="light" title={`${a.topic_label} — ${a.district}`}>
                      {a.message}
                    </Alert>
                  ))}
                </Stack>
              </Card>
            )}

            {(crosscheck?.topics as CrosscheckTopic[] ?? []).map((topic) => (
              <Card key={topic.topic} withBorder padding="md">
                <Group justify="space-between" mb="sm">
                  <div>
                    <Text fw={600}>{topic.label}</Text>
                    <Text size="xs" c="dimmed">{topic.articles} · поручений МВК: {topic.assignments_count}</Text>
                  </div>
                  {topic.worst_district && (
                    <Badge color="red" variant="light">
                      Худший: {topic.worst_district} ({topic.worst_count})
                    </Badge>
                  )}
                </Group>
                <Table striped>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Район</Table.Th>
                      <Table.Th>Показатель</Table.Th>
                      <Table.Th>Охват МВК</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {topic.districts.map((d) => (
                      <Table.Tr key={`${topic.topic}-${d.district}`}>
                        <Table.Td>{d.district}</Table.Td>
                        <Table.Td>{d.stat_count}</Table.Td>
                        <Table.Td>
                          <Badge color={d.mvk_covered ? "teal" : "red"} variant="light">
                            {d.mvk_covered ? "охвачен" : "пропущен"}
                          </Badge>
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Card>
            ))}
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="law">
          <Stack gap="md">
            {law?.overall_score != null && (
              <StatCard
                icon={<IconScale size={24} />}
                label="Сводный индекс соблюдения ключевых норм"
                value={`${law.overall_score}%`}
                color={law.overall_score >= 70 ? "teal" : "orange"}
              />
            )}

            <Card withBorder padding="md">
              <Table striped highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Закон</Table.Th>
                    <Table.Th>Статья</Table.Th>
                    <Table.Th>Требование</Table.Th>
                    <Table.Th>Показатель</Table.Th>
                    <Table.Th>Вывод</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {(law?.norms as LawNorm[] ?? []).map((n, i) => (
                    <Table.Tr key={i}>
                      <Table.Td>{n.law}</Table.Td>
                      <Table.Td><Badge variant="outline">{n.article}</Badge></Table.Td>
                      <Table.Td><Text size="sm">{n.requirement}</Text></Table.Td>
                      <Table.Td>
                        {n.compliance_pct != null ? (
                          <Group gap="xs">
                            <Text fw={600}>{n.inverted ? n.numerator : `${n.compliance_pct}%`}</Text>
                            <Text size="xs" c="dimmed">{n.numerator}/{n.denominator}</Text>
                          </Group>
                        ) : (
                          <Text size="sm">{n.numerator} по {n.by_district?.length ?? 0} районам</Text>
                        )}
                      </Table.Td>
                      <Table.Td>
                        <Badge
                          color={
                            n.verdict === "соблюдается" || n.verdict === "без повторов" || n.verdict === "мониторинг"
                              ? "teal"
                              : n.verdict === "требует контроля"
                                ? "yellow"
                                : "red"
                          }
                          variant="light"
                        >
                          {n.verdict}
                        </Badge>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Card>

            {(law?.norms as LawNorm[] ?? [])
              .filter((n) => n.by_district?.length)
              .map((n) => (
                <Card key={n.article} withBorder padding="md">
                  <Text fw={600} mb="sm">{n.article} — топ районов</Text>
                  <Group gap="xs">
                    {n.by_district!.map((d) => (
                      <Badge key={d.district} variant="light" color="orange">
                        {d.district}: {d.count}
                      </Badge>
                    ))}
                  </Group>
                </Card>
              ))}
          </Stack>
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
