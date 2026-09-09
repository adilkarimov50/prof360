import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  FileInput,
  Group,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
} from "@mantine/core";
import { IconUpload } from "@tabler/icons-react";
import api from "../api";
import { useAuth } from "../auth";
import PageHeader from "../components/PageHeader";
import { PageLoader } from "../components/LoadingSkeleton";
import ErrorState from "../components/ErrorState";
import type { CommissionDocument } from "../types/api";

const DOC_TYPES = [
  { value: "protocol", label: "Протокол заседания" },
  { value: "report", label: "Доклад" },
  { value: "execution_plan", label: "План исполнения" },
];

const UPLOAD_ROLES = new Set([
  "admin",
  "analyst",
  "oblast_prosecutor",
  "deputy_prosecutor",
  "district_prosecutor",
]);

const STATUS_COLORS: Record<string, string> = {
  uploaded: "gray",
  analyzing: "blue",
  analyzed: "teal",
  error: "red",
};

const STATUS_LABELS: Record<string, string> = {
  uploaded: "Загружен",
  analyzing: "Анализ…",
  analyzed: "Проанализирован",
  error: "Ошибка",
};

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

export default function CommissionDocs() {
  const { user } = useAuth();
  const canUpload = user?.role && UPLOAD_ROLES.has(user.role);

  const [docs, setDocs] = useState<CommissionDocument[]>([]);
  const [districts, setDistricts] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [docType, setDocType] = useState<string | null>("protocol");
  const [district, setDistrict] = useState<string | null>(user?.district || null);
  const [period, setPeriod] = useState("");
  const [sessionDate, setSessionDate] = useState("");
  const [title, setTitle] = useState("");

  const [filterDistrict, setFilterDistrict] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<string | null>(null);

  const loadDocs = useCallback(async () => {
    try {
      const params: Record<string, string> = {};
      if (filterDistrict) params.district = filterDistrict;
      if (filterType) params.doc_type = filterType;
      const { data } = await api.get<CommissionDocument[]>("/commission/documents", { params });
      setDocs(data);
      setError("");
    } catch {
      setError("Не удалось загрузить список документов");
    }
  }, [filterDistrict, filterType]);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      loadDocs(),
      api.get("/dashboard/overview").then((r) => {
        const list = (r.data.district_risk || []).map((d: { district: string }) => d.district);
        setDistricts(list);
      }).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, [loadDocs]);

  const hasAnalyzing = useMemo(() => docs.some((d) => d.status === "analyzing"), [docs]);

  useEffect(() => {
    if (!hasAnalyzing) return;
    const t = setInterval(loadDocs, 4000);
    return () => clearInterval(t);
  }, [hasAnalyzing, loadDocs]);

  const handleUpload = async () => {
    if (!file || !docType || !district || !period.trim()) return;
    setUploading(true);
    setUploadError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("doc_type", docType);
      fd.append("district", district);
      fd.append("period", period.trim());
      if (sessionDate) fd.append("session_date", sessionDate);
      if (title.trim()) fd.append("title", title.trim());
      await api.post("/commission/documents", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setFile(null);
      setTitle("");
      await loadDocs();
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setUploadError(typeof msg === "string" ? msg : "Ошибка загрузки документа");
    } finally {
      setUploading(false);
    }
  };

  if (loading && !docs.length) return <PageLoader />;
  if (error && !docs.length) return <ErrorState message={error} />;

  return (
    <Stack gap="md">
      <PageHeader
        title="Комиссия по профилактике"
        subtitle="Загрузка протоколов, докладов и планов исполнения с ИИ-анализом"
      />

      {canUpload && (
        <Card withBorder padding="lg">
          <Stack gap="sm">
            <Alert color="orange" title="Внешний ИИ (Gemini multimodal)">
              При анализе PDF и сканов оригинал документа (в т.ч. с персональными данными) передаётся
              во внешний сервис Google Gemini без локального обезличивания. Действие фиксируется в журнале аудита.
              Формат Word — только <strong>.docx</strong> (старый .doc конвертируйте в PDF или DOCX).
            </Alert>
            <FileInput
              label="Документ (PDF, DOCX, JPG, PNG, до 20 МБ)"
              value={file}
              onChange={setFile}
              accept=".pdf,.docx,.jpg,.jpeg,.png"
              leftSection={<IconUpload size={16} />}
            />
            <Group grow align="flex-start">
              <Select label="Тип документа" data={DOC_TYPES} value={docType} onChange={setDocType} required />
              <Select
                label="Район"
                data={districts}
                value={district}
                onChange={setDistrict}
                searchable
                required
                disabled={!!user?.district}
              />
              <TextInput label="Период" placeholder="2025-Q1 / 2025 год" value={period} onChange={(e) => setPeriod(e.currentTarget.value)} required />
            </Group>
            <Group grow align="flex-start">
              <TextInput label="Дата заседания" type="date" value={sessionDate} onChange={(e) => setSessionDate(e.currentTarget.value)} />
              <TextInput label="Название (необязательно)" value={title} onChange={(e) => setTitle(e.currentTarget.value)} />
            </Group>
            <Button onClick={handleUpload} loading={uploading} disabled={!file || !docType || !district || !period.trim()}>
              Загрузить и запустить анализ
            </Button>
            {uploadError && <Alert color="red">{uploadError}</Alert>}
          </Stack>
        </Card>
      )}

      <Card withBorder padding="lg">
        <Group mb="md">
          <Select placeholder="Фильтр: район" clearable searchable data={districts} value={filterDistrict} onChange={setFilterDistrict} w={220} />
          <Select placeholder="Фильтр: тип" clearable data={DOC_TYPES} value={filterType} onChange={setFilterType} w={220} />
          <Button variant="light" onClick={loadDocs}>Обновить</Button>
        </Group>
        {error && <Alert color="red" mb="sm">{error}</Alert>}
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Документ</Table.Th>
              <Table.Th>Тип</Table.Th>
              <Table.Th>Район</Table.Th>
              <Table.Th>Период</Table.Th>
              <Table.Th>Статус</Table.Th>
              <Table.Th>Качество</Table.Th>
              <Table.Th>Закон</Table.Th>
              <Table.Th>Эффективность</Table.Th>
              <Table.Th>Рекомендация</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {docs.length === 0 && (
              <Table.Tr><Table.Td colSpan={9}><Text c="dimmed">Документов пока нет</Text></Table.Td></Table.Tr>
            )}
            {docs.map((d) => (
              <Table.Tr key={d.id}>
                <Table.Td>
                  <Anchor component={Link} to={`/commission/${d.id}`}>
                    {d.title || d.original_filename}
                  </Anchor>
                </Table.Td>
                <Table.Td>{DOC_TYPES.find((t) => t.value === d.doc_type)?.label || d.doc_type}</Table.Td>
                <Table.Td>{d.district}</Table.Td>
                <Table.Td>{d.period}</Table.Td>
                <Table.Td>
                  <Badge color={STATUS_COLORS[d.status] || "gray"}>{STATUS_LABELS[d.status] || d.status}</Badge>
                </Table.Td>
                <Table.Td>{d.quality_score != null ? d.quality_score.toFixed(0) : "—"}</Table.Td>
                <Table.Td>
                  {d.legal_compliance_score != null ? (
                    <Badge color={d.legal_compliance_score >= 70 ? "green" : d.legal_compliance_score >= 40 ? "yellow" : "red"}>
                      {d.legal_compliance_score.toFixed(0)}
                    </Badge>
                  ) : "—"}
                </Table.Td>
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
      </Card>
    </Stack>
  );
}
