import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Group,
  Loader,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Accordion,
} from "@mantine/core";
import {
  IconChartBar,
  IconPlus,
  IconRefresh,
} from "@tabler/icons-react";
import api from "../api";
import PageHeader from "../components/PageHeader";
import { PageLoader } from "../components/LoadingSkeleton";
import ErrorState from "../components/ErrorState";
import StatCard from "../components/StatCard";

const TYPE_LABELS: Record<string, string> = {
  ordinary: "Очередное",
  extraordinary: "Внеочередное",
};

const GRADE_COLORS: Record<string, string> = {
  A: "green", B: "teal", C: "yellow", D: "orange", F: "red",
};

const GOALS_COLORS: Record<string, string> = {
  yes: "green", partial: "yellow", no: "red", unknown: "gray",
};

const GOALS_LABELS: Record<string, string> = {
  yes: "Цели достигнуты", partial: "Частично", no: "Не достигнуты", unknown: "Не оценено",
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

function completionColor(rate: number | null | undefined): string {
  if (rate == null) return "gray";
  if (rate >= 70) return "green";
  if (rate >= 45) return "yellow";
  return "red";
}

interface AssignmentRow {
  id: number;
  point_number: string;
  text: string;
  topic: string | null;
  executions_count: number;
  completion_rate: number | null;
}

interface SessionDetailCache {
  assignments: AssignmentRow[];
  title?: string | null;
}

function SessionAssignmentsTable({ sessionId }: { sessionId: number }) {
  const [detail, setDetail] = useState<SessionDetailCache | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError("");
    api.get(`/commission-sessions/${sessionId}`)
      .then(({ data }) => {
        if (cancelled) return;
        setDetail({
          title: data.title,
          assignments: data.assignments || [],
        });
      })
      .catch(() => {
        if (!cancelled) setLoadError("Не удалось загрузить поручения");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [sessionId]);

  if (loading) {
    return (
      <Group justify="center" py="sm">
        <Loader size="sm" />
        <Text size="sm" c="dimmed">Загрузка поручений…</Text>
      </Group>
    );
  }

  if (loadError) {
    return <Alert color="red" variant="light">{loadError}</Alert>;
  }

  const assignments = detail?.assignments ?? [];
  if (!assignments.length) {
    return <Text size="sm" c="dimmed">Поручения не загружены для этого заседания.</Text>;
  }

  return (
    <Stack gap="xs">
      {detail?.title && (
        <Text size="sm" c="dimmed">{detail.title}</Text>
      )}
      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>П.№</Table.Th>
            <Table.Th>Тема</Table.Th>
            <Table.Th>Поручение</Table.Th>
            <Table.Th>Исполнение</Table.Th>
            <Table.Th>%</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {assignments.map((a) => (
            <Table.Tr key={a.id}>
              <Table.Td>
                <Badge variant="outline" color="blue">П.{a.point_number}</Badge>
              </Table.Td>
              <Table.Td>
                <Badge variant="light" color="gray" size="sm">
                  {TOPIC_LABELS[a.topic || ""] || a.topic || "—"}
                </Badge>
              </Table.Td>
              <Table.Td>
                <Text size="sm" lineClamp={2}>{a.text}</Text>
              </Table.Td>
              <Table.Td>
                {a.executions_count > 0
                  ? `${a.executions_count} ${a.executions_count === 1 ? "орган" : "органов"}`
                  : "0 ответов"}
              </Table.Td>
              <Table.Td>
                <Badge color={completionColor(a.completion_rate)}>
                  {a.completion_rate != null ? `${a.completion_rate.toFixed(0)}%` : "—"}
                </Badge>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Stack>
  );
}

interface SessionRow {
  id: number;
  session_number: string;
  session_date: string | null;
  session_type: string;
  quarter: number | null;
  year: number | null;
  effectiveness_score: number | null;
  assignments_count: number;
  executions_count: number;
  grade: string | null;
  goals_achieved: string | null;
}

export default function CommissionSessions() {
  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [crossReport, setCrossReport] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [yearFilter, setYearFilter] = useState<string | null>(null);
  const [quarterFilter, setQuarterFilter] = useState<string | null>(null);

  const [ingestFolder, setIngestFolder] = useState("");
  const [ingestType, setIngestType] = useState<string>("ordinary");
  const [ingesting, setIngesting] = useState(false);
  const [ingestResult, setIngestResult] = useState<any>(null);
  const [ingestError, setIngestError] = useState<string | null>(null);

  const load = async () => {
    try {
      const params: Record<string, string> = {};
      if (yearFilter) params.year = yearFilter;
      if (quarterFilter) params.quarter = quarterFilter;
      const [sessResp, crResp] = await Promise.all([
        api.get<SessionRow[]>("/commission-sessions/", { params }),
        api.get("/commission-sessions/cross-report", { params: yearFilter ? { year: yearFilter } : {} }),
      ]);
      setSessions(sessResp.data);
      setCrossReport(crResp.data);
      setError("");
    } catch {
      setError("Не удалось загрузить данные");
    }
  };

  useEffect(() => {
    setLoading(true);
    load().finally(() => setLoading(false));
  }, [yearFilter, quarterFilter]);

  const handleIngest = async () => {
    if (!ingestFolder.trim()) return;
    setIngesting(true);
    setIngestError(null);
    setIngestResult(null);
    try {
      const { data } = await api.post("/commission-sessions/ingest", {
        folder_path: ingestFolder.trim(),
        session_type: ingestType,
        force: false,
      });
      setIngestResult(data);
      await load();
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setIngestError(typeof msg === "string" ? msg : "Ошибка импорта");
    } finally {
      setIngesting(false);
    }
  };

  const handleAnalyze = async (sessionId: number) => {
    try {
      await api.post(`/commission-sessions/${sessionId}/assess`);
      await api.post(`/commission-sessions/${sessionId}/analyze`);
      await load();
    } catch {
      setError("Ошибка при запуске анализа");
    }
  };

  if (loading && !sessions.length) return <PageLoader />;
  if (error && !sessions.length) return <ErrorState message={error} />;

  const byQuarter: Record<string, SessionRow[]> = {};
  for (const s of sessions) {
    const key = s.year ? `${s.year} — Q${s.quarter ?? "?"}` : "Без даты";
    byQuarter[key] = [...(byQuarter[key] || []), s];
  }

  return (
    <Stack gap="md">
      <PageHeader
        title="Заседания МВК"
        subtitle="Протоколы, поручения, исполнение по органам и оценка эффективности"
      />

      {/* Импорт документов */}
      <Card withBorder padding="lg">
        <Text fw={600} mb="sm">Импорт документов МВК из папки</Text>
        <Alert color="blue" mb="sm">
          Укажите полный путь к папке с документами комиссии (.docx). Система автоматически определит
          протоколы, извлечёт поручения и ответы органов с помощью ИИ.
        </Alert>
        <Group align="flex-end">
          <TextInput
            label="Путь к папке"
            placeholder="/Users/user/prof/Комиссия по профилактике 2 заседания 2026 года"
            value={ingestFolder}
            onChange={(e) => setIngestFolder(e.currentTarget.value)}
            style={{ flex: 1 }}
          />
          <Select
            label="Тип заседания"
            data={[
              { value: "ordinary", label: "Очередное" },
              { value: "extraordinary", label: "Внеочередное" },
            ]}
            value={ingestType}
            onChange={(v) => setIngestType(v || "ordinary")}
            w={200}
          />
          <Button leftSection={<IconPlus size={16} />} onClick={handleIngest} loading={ingesting}>
            Импортировать
          </Button>
        </Group>
        {ingestError && <Alert color="red" mt="sm">{ingestError}</Alert>}
        {ingestResult && (
          <Alert color="teal" mt="sm" title="Импорт завершён">
            {JSON.stringify(ingestResult, null, 2)}
          </Alert>
        )}
      </Card>

      {/* Фильтры */}
      <Group>
        <Select placeholder="Год" clearable data={["2025", "2026", "2027"]} value={yearFilter} onChange={setYearFilter} w={120} />
        <Select placeholder="Квартал" clearable data={["1", "2", "3", "4"]} value={quarterFilter} onChange={setQuarterFilter} w={140} />
        <Button variant="light" leftSection={<IconRefresh size={16} />} onClick={load}>Обновить</Button>
      </Group>

      {/* Сводная статистика */}
      {crossReport && (
        <Card withBorder padding="lg">
          <Text fw={600} mb="md">Сводный отчёт по органам</Text>
          {crossReport.organ_ratings && crossReport.organ_ratings.length > 0 ? (
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Орган</Table.Th>
                  <Table.Th>Ср. балл исполнения</Table.Th>
                  <Table.Th>Сессий</Table.Th>
                  <Table.Th>Оценка</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {crossReport.organ_ratings.map((r: any) => (
                  <Table.Tr key={r.organ}>
                    <Table.Td>{r.organ}</Table.Td>
                    <Table.Td>
                      <Badge color={r.avg_score >= 70 ? "green" : r.avg_score >= 45 ? "yellow" : "red"}>
                        {r.avg_score.toFixed(0)}
                      </Badge>
                    </Table.Td>
                    <Table.Td>{r.sessions_count}</Table.Td>
                    <Table.Td>
                      {r.avg_score < 35 ? <Badge color="red">Не исполняет</Badge> :
                       r.avg_score < 55 ? <Badge color="orange">Формально</Badge> :
                       r.avg_score < 75 ? <Badge color="yellow">Частично</Badge> :
                       <Badge color="green">Исполняет</Badge>}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          ) : (
            <Text c="dimmed">После анализа заседаний здесь появится рейтинг органов</Text>
          )}
        </Card>
      )}

      {/* Список заседаний по кварталам */}
      {sessions.length === 0 ? (
        <Alert color="gray">
          Заседания не загружены. Используйте форму импорта выше, чтобы загрузить папку документов МВК.
        </Alert>
      ) : (
        <Accordion variant="separated">
          {Object.entries(byQuarter).map(([quarter, qSessions]) => (
            <Accordion.Item key={quarter} value={quarter}>
              <Accordion.Control>
                <Group>
                  <Text fw={600}>{quarter}</Text>
                  <Badge>{qSessions.length} заседаний</Badge>
                </Group>
              </Accordion.Control>
              <Accordion.Panel>
                <Accordion variant="contained" chevronPosition="left">
                  {qSessions.map((s) => (
                    <Accordion.Item key={s.id} value={String(s.id)}>
                      <Accordion.Control>
                        <Group justify="space-between" wrap="nowrap" pr="md">
                          <div>
                            <Group gap="sm">
                              <Text fw={700}>Протокол №{s.session_number}</Text>
                              <Badge variant="light" color={s.session_type === "extraordinary" ? "orange" : "blue"}>
                                {TYPE_LABELS[s.session_type] || s.session_type}
                              </Badge>
                              {s.grade && <Badge color={GRADE_COLORS[s.grade] || "gray"}>Оценка: {s.grade}</Badge>}
                              {s.goals_achieved && (
                                <Badge color={GOALS_COLORS[s.goals_achieved] || "gray"}>
                                  {GOALS_LABELS[s.goals_achieved] || s.goals_achieved}
                                </Badge>
                              )}
                            </Group>
                            <Text size="sm" c="dimmed" mt={4}>
                              {s.session_date || "Дата не указана"} ·{" "}
                              {s.assignments_count} поручений · {s.executions_count} ответов органов
                            </Text>
                          </div>
                          {s.effectiveness_score != null && (
                            <Badge size="lg" color={s.effectiveness_score >= 70 ? "green" : s.effectiveness_score >= 45 ? "yellow" : "red"}>
                              {s.effectiveness_score.toFixed(0)}%
                            </Badge>
                          )}
                        </Group>
                      </Accordion.Control>
                      <Accordion.Panel>
                        <Stack gap="sm">
                          <SessionAssignmentsTable sessionId={s.id} />
                          <Group>
                            <Button
                              size="xs"
                              variant="light"
                              leftSection={<IconChartBar size={14} />}
                              onClick={() => handleAnalyze(s.id)}
                            >
                              Проанализировать
                            </Button>
                            <Button size="xs" component={Link} to={`/commission-sessions/${s.id}`}>
                              Детали →
                            </Button>
                            <Anchor component={Link} to={`/commission-sessions/${s.id}`} size="sm">
                              Полный протокол №{s.session_number}
                            </Anchor>
                          </Group>
                        </Stack>
                      </Accordion.Panel>
                    </Accordion.Item>
                  ))}
                </Accordion>
              </Accordion.Panel>
            </Accordion.Item>
          ))}
        </Accordion>
      )}
    </Stack>
  );
}
