import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Accordion,
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Group,
  List,
  ScrollArea,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import {
  IconArrowLeft,
  IconChartBar,
  IconCheck,
  IconX,
  IconAlertTriangle,
} from "@tabler/icons-react";
import api from "../api";
import { PageLoader } from "../components/LoadingSkeleton";
import ErrorState from "../components/ErrorState";
import StatCard from "../components/StatCard";

const STATUS_LABELS: Record<string, string> = {
  executed: "Исполнено",
  partial: "Частично",
  formal: "Формально",
  not_executed: "Не исполнено",
  unknown: "Не оценено",
};

const STATUS_COLORS: Record<string, string> = {
  executed: "green",
  partial: "yellow",
  formal: "orange",
  not_executed: "red",
  unknown: "gray",
};

const TOPIC_LABELS: Record<string, string> = {
  cyber: "Интернет-мошенничество",
  extortion: "Вымогательство",
  juvenile: "Несовершеннолетние",
  vape: "Вейп (ст.301-1)",
  alcohol: "Алкоголь/детокс",
  road: "Дорожная безопасность",
  law: "Новый закон о профилактике",
  other: "Иное",
};

const GRADE_COLORS: Record<string, string> = {
  A: "green", B: "teal", C: "yellow", D: "orange", F: "red",
};

const GOALS_LABELS: Record<string, string> = {
  yes: "Цели достигнуты",
  partial: "Частично достигнуты",
  no: "Цели не достигнуты",
  unknown: "Не оценено",
};

export default function CommissionSessionDetail() {
  const { id } = useParams();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [analyzing, setAnalyzing] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const { data: d } = await api.get(`/commission-sessions/${id}`);
      setData(d);
      setError("");
    } catch {
      setError("Не удалось загрузить заседание");
    }
  }, [id]);

  useEffect(() => {
    setLoading(true);
    load().finally(() => setLoading(false));
  }, [load]);

  const handleAnalyze = async () => {
    if (!id) return;
    setAnalyzing(true);
    try {
      await api.post(`/commission-sessions/${id}/assess`);
      const { data: analysisData } = await api.post(`/commission-sessions/${id}/analyze`);
      setData((prev: any) => ({ ...prev, ai_analysis: analysisData?.ai_analysis }));
      await load();
    } catch {
      setError("Ошибка при запуске анализа");
    } finally {
      setAnalyzing(false);
    }
  };

  if (loading) return <PageLoader />;
  if (error || !data) return <ErrorState message={error || "Заседание не найдено"} />;

  const ai = data.ai_analysis;
  const matrix: Record<string, Record<string, any>> = data.matrix || {};
  const organs = Object.keys(matrix);
  const assignments = data.assignments || [];
  const underperformers = data.underperforming_organs || [];

  return (
    <Stack gap="md">
      <Anchor component={Link} to="/commission-sessions" size="sm">
        <IconArrowLeft size={14} style={{ verticalAlign: "middle" }} /> К списку заседаний
      </Anchor>

      <Group justify="space-between" align="flex-start">
        <div>
          <Title order={2}>Протокол №{data.session_number}</Title>
          <Text c="dimmed">
            {data.session_date || "Дата не указана"} ·{" "}
            {data.session_type === "extraordinary" ? "Внеочередное" : "Очередное"} заседание ·{" "}
            Q{data.quarter ?? "?"} {data.year}
          </Text>
        </div>
        <Button leftSection={<IconChartBar size={16} />} onClick={handleAnalyze} loading={analyzing}>
          {ai ? "Переанализировать" : "Запустить ИИ-анализ"}
        </Button>
      </Group>

      {/* Сводка */}
      <SimpleGrid cols={{ base: 2, sm: 4 }}>
        <StatCard icon={<IconChartBar size={24}/>} label="Поручений" value={data.assignments_count} color="blue" />
        <StatCard icon={<IconCheck size={24}/>} label="Ответов органов" value={data.executions_count} color="teal" />
        {data.effectiveness_score != null && (
          <StatCard icon={<IconChartBar size={24}/>} label="Балл исполнения" value={`${data.effectiveness_score.toFixed(0)}%`}
            color={data.effectiveness_score >= 70 ? "green" : data.effectiveness_score >= 45 ? "yellow" : "red"} />
        )}
        {data.grade && (
          <StatCard icon={<IconCheck size={24}/>} label="Оценка МВК" value={data.grade}
            color={GRADE_COLORS[data.grade] || "gray"} />
        )}
      </SimpleGrid>

      {/* AI-заключение */}
      {ai && (
        <Card withBorder padding="lg">
          <Group mb="md">
            <Title order={4}>ИИ-заключение прокурора-аналитика</Title>
            <Badge color={GRADE_COLORS[ai.overall_grade] || "gray"} size="lg">
              Оценка: {ai.overall_grade}
            </Badge>
            {ai.goals_achieved && (
              <Badge color={ai.goals_achieved === "yes" ? "green" : ai.goals_achieved === "partial" ? "yellow" : "red"}>
                {GOALS_LABELS[ai.goals_achieved] || ai.goals_achieved}
              </Badge>
            )}
          </Group>

          {ai.overall_comment && (
            <Alert color="blue" mb="md" title="Итоговый вывод">
              {ai.overall_comment}
            </Alert>
          )}

          {ai.goals_summary && (
            <>
              <Text fw={600} mb="xs">Достижение целей</Text>
              <Text mb="md">{ai.goals_summary}</Text>
            </>
          )}

          {ai.direction_assessment && (
            <Alert
              color={ai.direction_assessment === "right" ? "green" : ai.direction_assessment === "wrong" ? "red" : "yellow"}
              mb="md"
              title={`Направление работы МВК: ${ai.direction_assessment === "right" ? "верное" : ai.direction_assessment === "needs_correction" ? "требует корректировки" : "неверное"}`}
            >
              {ai.direction_comment}
            </Alert>
          )}

          {Array.isArray(ai.critical_failures) && ai.critical_failures.length > 0 && (
            <>
              <Text fw={600} c="red" mb="xs">Критические нарушения исполнения</Text>
              <List icon={<IconX size={14} color="red" />} mb="md">
                {ai.critical_failures.map((f: string, i: number) => <List.Item key={i}>{f}</List.Item>)}
              </List>
            </>
          )}

          {Array.isArray(ai.missed_priorities) && ai.missed_priorities.length > 0 && (
            <>
              <Text fw={600} c="orange" mb="xs">Приоритеты, которые МВК не охватывает</Text>
              <List icon={<IconAlertTriangle size={14} color="orange" />} mb="md">
                {ai.missed_priorities.map((f: string, i: number) => <List.Item key={i}>{f}</List.Item>)}
              </List>
            </>
          )}

          {Array.isArray(ai.recommendations) && ai.recommendations.length > 0 && (
            <>
              <Text fw={600} c="teal" mb="xs">Рекомендации</Text>
              <List icon={<IconCheck size={14} color="teal" />}>
                {ai.recommendations.map((r: string, i: number) => <List.Item key={i}>{r}</List.Item>)}
              </List>
            </>
          )}
        </Card>
      )}

      {/* Органы с низкими показателями */}
      {underperformers.length > 0 && (
        <Card withBorder padding="md">
          <Text fw={600} mb="sm" c="red">Органы с недостаточным исполнением</Text>
          <Table striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Орган</Table.Th>
                <Table.Th>Ср. балл</Table.Th>
                <Table.Th>Пунктов</Table.Th>
                <Table.Th>Формально/не исп.</Table.Th>
                <Table.Th>Уровень</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {underperformers.map((u: any) => (
                <Table.Tr key={u.organ}>
                  <Table.Td>{u.organ}</Table.Td>
                  <Table.Td>
                    <Badge color={u.avg_score < 30 ? "red" : u.avg_score < 55 ? "orange" : "yellow"}>
                      {u.avg_score.toFixed(0)}
                    </Badge>
                  </Table.Td>
                  <Table.Td>{u.points_count}</Table.Td>
                  <Table.Td>{u.formal_or_no_response}</Table.Td>
                  <Table.Td>
                    <Badge color={u.level === "critical" ? "red" : u.level === "low" ? "orange" : "yellow"}>
                      {u.level === "critical" ? "Критический" : u.level === "low" ? "Низкий" : "Средний"}
                    </Badge>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Card>
      )}

      {/* Матрица исполнения */}
      {organs.length > 0 && (
        <Card withBorder padding="md">
          <Text fw={600} mb="sm">Матрица исполнения: орган × поручение</Text>
          <ScrollArea>
            <Table striped highlightOnHover style={{ minWidth: 800 }}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th style={{ minWidth: 200 }}>Орган</Table.Th>
                  {assignments.map((a: any) => (
                    <Table.Th key={a.id} style={{ minWidth: 80, textAlign: "center" }}>
                      <Text size="xs">П.{a.point_number}</Text>
                      <Text size="xs" c="dimmed" fw={400}>{TOPIC_LABELS[a.topic] || a.topic}</Text>
                    </Table.Th>
                  ))}
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {organs.map((organ) => (
                  <Table.Tr key={organ}>
                    <Table.Td>{organ}</Table.Td>
                    {assignments.map((a: any) => {
                      const entry = matrix[organ]?.[a.point_number];
                      return (
                        <Table.Td key={a.id} style={{ textAlign: "center" }}>
                          {entry ? (
                            <Badge
                              size="sm"
                              color={STATUS_COLORS[entry.status] || "gray"}
                              title={entry.assessment || ""}
                            >
                              {STATUS_LABELS[entry.status]?.slice(0, 6) || entry.status}
                            </Badge>
                          ) : <Text size="xs" c="dimmed">—</Text>}
                        </Table.Td>
                      );
                    })}
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea>
        </Card>
      )}

      {/* Поручения с детализацией */}
      <Accordion variant="separated">
        {assignments.map((a: any) => (
          <Accordion.Item key={a.id} value={String(a.id)}>
            <Accordion.Control>
              <Group>
                <Badge color="blue">П.{a.point_number}</Badge>
                {a.topic && <Badge variant="light" color="gray">{TOPIC_LABELS[a.topic] || a.topic}</Badge>}
                {a.completion_rate != null && (
                  <Badge color={a.completion_rate >= 70 ? "green" : a.completion_rate >= 45 ? "yellow" : "red"}>
                    {a.completion_rate.toFixed(0)}%
                  </Badge>
                )}
                <Text size="sm" lineClamp={1}>{a.text?.slice(0, 120)}</Text>
              </Group>
            </Accordion.Control>
            <Accordion.Panel>
              <Stack gap="sm">
                <Text size="sm">{a.text}</Text>
                {a.responsible_organs && <Text size="sm" c="dimmed">Ответственные: {a.responsible_organs}</Text>}
                {a.deadline && <Text size="sm" c="dimmed">Срок: {a.deadline}</Text>}
                <ExecutionsList assignmentId={a.id} sessionId={Number(id)} />
              </Stack>
            </Accordion.Panel>
          </Accordion.Item>
        ))}
      </Accordion>

      {assignments.length === 0 && (
        <Alert color="orange">
          Поручения не загружены. Запустите импорт документов МВК.
        </Alert>
      )}
    </Stack>
  );
}

function ExecutionsList({ assignmentId, sessionId }: { assignmentId: number; sessionId: number }) {
  const [executions, setExecutions] = useState<any[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.get(`/commission-sessions/${sessionId}/assignments/${assignmentId}/executions`)
      .then(({ data }) => {
        if (!cancelled) setExecutions(data);
      })
      .catch(() => {
        if (!cancelled) setExecutions([]);
      })
      .finally(() => {
        if (!cancelled) setLoaded(true);
      });
    return () => { cancelled = true; };
  }, [assignmentId, sessionId]);

  if (!loaded) {
    return (
      <Group gap="xs">
        <Text size="sm" c="dimmed">Загрузка ответов органов…</Text>
      </Group>
    );
  }

  if (!executions.length) return <Text size="sm" c="dimmed">Ответов органов нет</Text>;

  return (
    <Table striped>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Орган</Table.Th>
          <Table.Th>Статус</Table.Th>
          <Table.Th>Балл</Table.Th>
          <Table.Th>Оценка ИИ</Table.Th>
          <Table.Th>Замечания</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {executions.map((e: any) => (
          <Table.Tr key={e.id}>
            <Table.Td>{e.organ_name}</Table.Td>
            <Table.Td>
              <Badge size="sm" color={STATUS_COLORS[e.execution_status] || "gray"}>
                {STATUS_LABELS[e.execution_status] || e.execution_status}
              </Badge>
            </Table.Td>
            <Table.Td>{e.quality_score != null ? e.quality_score.toFixed(0) : "—"}</Table.Td>
            <Table.Td style={{ maxWidth: 300 }}>
              <Text size="xs">{e.ai_assessment || "—"}</Text>
            </Table.Td>
            <Table.Td>
              {Array.isArray(e.issues) && e.issues.length > 0 ? (
                <List size="xs">
                  {e.issues.slice(0, 2).map((issue: string, i: number) => (
                    <List.Item key={i}><Text size="xs">{issue}</Text></List.Item>
                  ))}
                </List>
              ) : "—"}
            </Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}
