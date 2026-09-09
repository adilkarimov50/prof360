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
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { IconArrowLeft, IconDownload, IconRefresh } from "@tabler/icons-react";
import api from "../api";
import { useAuth } from "../auth";
import { PageLoader } from "../components/LoadingSkeleton";
import ErrorState from "../components/ErrorState";
import type { CommissionDocumentDetail, LegalAssignmentCheck } from "../types/api";

const UPLOAD_ROLES = new Set([
  "admin",
  "analyst",
  "oblast_prosecutor",
  "deputy_prosecutor",
  "district_prosecutor",
]);

const REC_LABELS: Record<string, string> = {
  yes: "Включать в протокол",
  revise: "С доработкой",
  no: "Не включать",
};

const REC_COLORS: Record<string, string> = {
  yes: "green",
  revise: "yellow",
  no: "red",
};

const REQUISITE_LABELS: Record<string, string> = {
  date: "Дата",
  commission_composition: "Состав комиссии",
  agenda: "Повестка",
  decisions: "Решения",
  deadlines: "Сроки",
  responsible_persons: "Ответственные",
  signatures: "Подписи",
};

const COMPLIANCE_LABELS: Record<string, string> = {
  ok: "Соответствует",
  warning: "Риски",
  violation: "Нарушение",
};

const COMPLIANCE_COLORS: Record<string, string> = {
  ok: "green",
  warning: "yellow",
  violation: "red",
};

function AssignmentLegalCard({ item }: { item: LegalAssignmentCheck }) {
  return (
    <Card withBorder padding="md" radius="md">
      <Group justify="space-between" mb="xs">
        <Badge color={COMPLIANCE_COLORS[item.compliance] || "gray"}>
          {COMPLIANCE_LABELS[item.compliance] || item.compliance}
        </Badge>
        {item.responsible && <Text size="sm" c="dimmed">Ответственный: {item.responsible}</Text>}
      </Group>
      <Text fw={500} mb="xs">{item.text}</Text>
      {item.deadline && <Text size="sm" c="dimmed" mb="xs">Срок: {item.deadline}</Text>}
      {item.execution_status && <Text size="sm" c="dimmed" mb="xs">Исполнение: {item.execution_status}</Text>}
      {item.matched_norms.length > 0 && (
        <>
          <Text fw={600} size="sm" mt="sm" mb="xs">Найденные нормы (векторный поиск)</Text>
          <Group gap="xs">
            {item.matched_norms.map((n) => (
              <Anchor key={n.norm_id} component={Link} to={`/legal/norms/${n.norm_id}`}>
                <Badge
                  variant="outline"
                  color={n.status === "действует" ? "teal" : "red"}
                  title={n.similarity != null ? `similarity: ${n.similarity}` : undefined}
                >
                  {n.ref || `#${n.norm_id}`}
                </Badge>
              </Anchor>
            ))}
          </Group>
        </>
      )}
      {item.issues.length > 0 && (
        <>
          <Text fw={600} size="sm" mt="sm" mb="xs">Замечания</Text>
          <List size="sm">
            {item.issues.map((issue, i) => <List.Item key={i}>{issue}</List.Item>)}
          </List>
        </>
      )}
      {item.recommendation && (
        <Text size="sm" mt="sm" c="dimmed"><Text span fw={600}>Рекомendation: </Text>{item.recommendation}</Text>
      )}
    </Card>
  );
}

function RequisitesChecklist({ requisites }: { requisites?: Record<string, { present?: boolean; comment?: string; value?: string }> }) {
  if (!requisites) return <Text c="dimmed">Нет данных</Text>;
  return (
    <List spacing="xs">
      {Object.entries(requisites).map(([key, val]) => (
        <List.Item key={key} icon={<Badge size="xs" color={val?.present ? "green" : "red"}>{val?.present ? "✓" : "✗"}</Badge>}>
          <Text span fw={500}>{REQUISITE_LABELS[key] || key}: </Text>
          <Text span c="dimmed">{val?.comment || val?.value || (val?.present ? "есть" : "отсутствует")}</Text>
        </List.Item>
      ))}
    </List>
  );
}

export default function CommissionDocDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const canReanalyze = user?.role && UPLOAD_ROLES.has(user.role);

  const [doc, setDoc] = useState<CommissionDocumentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reanalyzing, setReanalyzing] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const { data } = await api.get<CommissionDocumentDetail>(`/commission/documents/${id}`);
      setDoc(data);
      setError("");
    } catch {
      setError("Не удалось загрузить документ");
    }
  }, [id]);

  useEffect(() => {
    setLoading(true);
    load().finally(() => setLoading(false));
  }, [load]);

  useEffect(() => {
    if (!doc || doc.status !== "analyzing") return;
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [doc?.status, load]);

  const handleReanalyze = async () => {
    if (!id) return;
    setReanalyzing(true);
    try {
      await api.post(`/commission/documents/${id}/reanalyze`);
      await load();
    } catch {
      setError("Не удалось запустить переанализ");
    } finally {
      setReanalyzing(false);
    }
  };

  const handleDownload = async () => {
    if (!id) return;
    const token = localStorage.getItem("access_token");
    const resp = await fetch(`/api/commission/documents/${id}/file`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!resp.ok) return;
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = doc?.original_filename || "document";
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) return <PageLoader />;
  if (error || !doc) return <ErrorState message={error || "Документ не найден"} />;

  const s1 = doc.analysis_document || {};
  const s2 = doc.analysis_execution || {};
  const legal = doc.analysis_legal;
  const justification = typeof s2.justification === "string" ? s2.justification : null;
  const summary1 = typeof s1.summary === "string" ? s1.summary : null;
  const assignmentsQuality = typeof s1.assignments_quality === "string" ? s1.assignments_quality : null;
  const summary2 = typeof s2.summary === "string" ? s2.summary : null;
  const executionAssessment = typeof s2.execution_assessment === "string" ? s2.execution_assessment : null;
  const feasibility = typeof s2.feasibility === "string" ? s2.feasibility : null;
  const effectiveness = typeof s2.effectiveness === "string" ? s2.effectiveness : null;
  const districtAlignment = typeof s2.district_alignment === "string" ? s2.district_alignment : null;
  const deficiencies = Array.isArray(s1.deficiencies) ? s1.deficiencies.filter((d): d is string => typeof d === "string") : [];
  const suggestions = Array.isArray(s2.suggestions) ? s2.suggestions.filter((s): s is string => typeof s === "string") : [];

  return (
    <Stack gap="md">
      <Anchor component={Link} to="/commission" size="sm">
        <IconArrowLeft size={14} style={{ verticalAlign: "middle" }} /> К списку документов
      </Anchor>

      <Group justify="space-between" align="flex-start">
        <div>
          <Title order={2}>{doc.title || doc.original_filename}</Title>
          <Text c="dimmed">{doc.district} · {doc.period} · {doc.doc_type}</Text>
        </div>
        <Group>
          <Button variant="light" leftSection={<IconDownload size={16} />} onClick={handleDownload}>
            Скачать оригинал
          </Button>
          {canReanalyze && (
            <Button leftSection={<IconRefresh size={16} />} loading={reanalyzing} onClick={handleReanalyze}
              disabled={doc.status === "analyzing"}>
              Переанализировать
            </Button>
          )}
        </Group>
      </Group>

      {doc.status === "analyzing" && (
        <Alert color="blue">Документ анализируется… Страница обновится автоматически.</Alert>
      )}
      {doc.status === "error" && (
        <Alert color="red" title="Ошибка анализа">{doc.error_message || "Неизвестная ошибка"}</Alert>
      )}

      {doc.include_recommendation && (
        <Alert color={REC_COLORS[doc.include_recommendation] || "gray"} title="Рекомендация о включении в протокол">
          <Badge size="lg" color={REC_COLORS[doc.include_recommendation]}>
            {REC_LABELS[doc.include_recommendation] || doc.include_recommendation}
          </Badge>
          {justification && <Text mt="sm">{justification}</Text>}
        </Alert>
      )}

      <Card withBorder padding="lg">
        <Group mb="md">
          <Title order={4}>Этап 1 — Анализ документа</Title>
          {doc.quality_score != null && <Badge size="lg">Качество: {doc.quality_score.toFixed(0)}/100</Badge>}
        </Group>
        {summary1 && <Text mb="md">{summary1}</Text>}
        <Text fw={600} mb="xs">Обязательные реквизиты</Text>
        <RequisitesChecklist requisites={s1.requisites as Record<string, { present?: boolean; comment?: string }>} />
        {assignmentsQuality && (
          <>
            <Text fw={600} mt="md" mb="xs">Качество поручений</Text>
            <Text>{assignmentsQuality}</Text>
          </>
        )}
        {deficiencies.length > 0 && (
          <>
            <Text fw={600} mt="md" mb="xs">Недостатки</Text>
            <List>
              {deficiencies.map((d, i) => <List.Item key={i}>{d}</List.Item>)}
            </List>
          </>
        )}
      </Card>

      {(legal || doc.legal_compliance_score != null) && (
        <Card withBorder padding="lg">
          <Group mb="md">
            <Title order={4}>Соответствие законодательству</Title>
            {doc.legal_compliance_score != null && (
              <Badge size="lg">Балл: {doc.legal_compliance_score.toFixed(0)}/100</Badge>
            )}
            {legal && legal.violations_count > 0 && (
              <Badge size="lg" color="red">Нарушений: {legal.violations_count}</Badge>
            )}
          </Group>
          {legal?.warnings && legal.warnings.length > 0 && (
            <Alert color="orange" mb="md">{legal.warnings.join(" ")}</Alert>
          )}
          {legal?.overall && <Text mb="md">{legal.overall}</Text>}
          {legal?.assignments && legal.assignments.length > 0 ? (
            <Stack gap="sm">
              {legal.assignments.map((a, i) => (
                <AssignmentLegalCard key={i} item={a} />
              ))}
            </Stack>
          ) : (
            <Text c="dimmed">Поручения для правовой проверки не извлечены.</Text>
          )}
        </Card>
      )}

      <Card withBorder padding="lg">
        <Group mb="md">
          <Title order={4}>Этап 2 — Исполнение и целесообразность</Title>
          {doc.effectiveness_score != null && (
            <Badge size="lg">Эффективность: {doc.effectiveness_score.toFixed(0)}/100</Badge>
          )}
        </Group>
        {summary2 && <Text mb="md">{summary2}</Text>}
        {executionAssessment && (
          <>
            <Text fw={600} mb="xs">Исполнение</Text>
            <Text>{executionAssessment}</Text>
          </>
        )}
        {feasibility && (
          <>
            <Text fw={600} mt="md" mb="xs">Целесообразность</Text>
            <Text>{feasibility}</Text>
          </>
        )}
        {effectiveness && (
          <>
            <Text fw={600} mt="md" mb="xs">Эффективность мер</Text>
            <Text>{effectiveness}</Text>
          </>
        )}
        {districtAlignment && (
          <>
            <Text fw={600} mt="md" mb="xs">Соответствие обстановке района</Text>
            <Text>{districtAlignment}</Text>
          </>
        )}
        {suggestions.length > 0 && (
          <>
            <Text fw={600} mt="md" mb="xs">Предложения</Text>
            <List>
              {suggestions.map((s, i) => <List.Item key={i}>{s}</List.Item>)}
            </List>
          </>
        )}
      </Card>

      {doc.extracted_text && (
        <Accordion variant="contained">
          <Accordion.Item value="text">
            <Accordion.Control>Распознанный текст</Accordion.Control>
            <Accordion.Panel>
              <Text style={{ whiteSpace: "pre-wrap", fontSize: "0.85rem" }}>{doc.extracted_text}</Text>
            </Accordion.Panel>
          </Accordion.Item>
        </Accordion>
      )}
    </Stack>
  );
}
