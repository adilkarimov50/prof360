import { useState } from "react";
import {
  Alert, Badge, Button, Card, FileInput, Group, Loader, NumberInput, Select, Stack, Table, Text, Title, SimpleGrid,
} from "@mantine/core";
import { IconUpload } from "@tabler/icons-react";
import api from "../api";
import PageHeader from "../components/PageHeader";
import StatCard from "../components/StatCard";
import { IconDatabase, IconUsers } from "@tabler/icons-react";

interface PreviewInfo {
  stored_name: string;
  file: string;
  type: string;
  headers: string[];
  suggested_map?: Record<string, number>;
  ai_hint?: string;
}

const ADMIN_FIELDS = [
  { key: "material_no", label: "Материал" },
  { key: "date", label: "Дата" },
  { key: "qual", label: "Квалификация" },
  { key: "surname", label: "Фамилия" },
  { key: "name", label: "Имя" },
  { key: "iin", label: "ИИН" },
  { key: "district", label: "Район" },
  { key: "decision", label: "Решение" },
  { key: "measure", label: "Мера" },
];

export default function Upload() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<PreviewInfo | null>(null);
  const [fileType, setFileType] = useState<string | null>(null);
  const [colmap, setColmap] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handlePreview = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post<PreviewInfo>("/ingest/preview", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setPreview(data);
      setFileType(data.type === "alcohol" ? "alcohol" : data.type);
      setColmap(data.suggested_map || {});
    } catch {
      setError("Не удалось проанализировать файл");
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    if (!preview || !fileType) return;
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.post("/ingest/confirm", {
        stored_name: preview.stored_name,
        file_type: fileType,
        column_map: Object.keys(colmap).length ? colmap : preview.suggested_map,
      });
      setResult(data);
    } catch {
      setError("Ошибка загрузки в базу");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Stack gap="md">
      <PageHeader title="Загрузка Excel" subtitle="Анализ колонок, ручной маппинг, отчёт качества после загрузки" />
      <Card withBorder padding="lg">
        <Stack gap="sm">
          <FileInput label="Файл Excel (.xlsx / .xls)" value={file} onChange={setFile} accept=".xlsx,.xls" leftSection={<IconUpload size={16} />} />
          <Group>
            <Button onClick={handlePreview} disabled={!file || loading}>Анализ колонок</Button>
            {preview && <Button color="teal" onClick={handleConfirm} disabled={loading || !fileType}>Загрузить в базу</Button>}
          </Group>
          {loading && <Loader size="sm" />}
        </Stack>
      </Card>
      {error && <Alert color="red">{error}</Alert>}
      {preview && (
        <Card withBorder padding="lg">
          <Stack gap="sm">
            <Group><Text fw={600}>{preview.file}</Text><Badge>{preview.type}</Badge></Group>
            <Select label="Тип загрузки" data={[
              { value: "admin", label: "Административная практика" },
              { value: "alcohol", label: "Алкоголь" },
              { value: "criminal", label: "ЕРДР / Книга46" },
              { value: "preventive", label: "Профучёт (.xls)" },
            ]} value={fileType} onChange={setFileType} />
            {preview.ai_hint && <Alert color="blue" title="Подсказка ИИ"><Text size="sm" style={{ whiteSpace: "pre-wrap" }}>{preview.ai_hint}</Text></Alert>}
            {(fileType === "admin" || fileType === "alcohol") && (
              <>
                <Text fw={500} size="sm">Маппинг колонок (индекс)</Text>
                <SimpleGrid cols={{ base: 1, sm: 2 }}>
                  {ADMIN_FIELDS.map((f) => (
                    <NumberInput key={f.key} label={f.label} min={0} max={preview.headers.length - 1} value={colmap[f.key] ?? ""} onChange={(v) => setColmap({ ...colmap, [f.key]: Number(v) })} />
                  ))}
                </SimpleGrid>
              </>
            )}
            <Table striped withTableBorder>
              <Table.Thead><Table.Tr><Table.Th>#</Table.Th><Table.Th>Колонка</Table.Th></Table.Tr></Table.Thead>
              <Table.Tbody>
                {preview.headers.map((h, i) => (
                  <Table.Tr key={i}><Table.Td>{i}</Table.Td><Table.Td>{h || "—"}</Table.Td></Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Stack>
        </Card>
      )}
      {result && (
        <>
          <Alert color="green" title="Загрузка завершена">
            Принято: {result.accepted}, отклонено: {result.rejected}, пересчитано лиц: {result.persons_scored}
          </Alert>
          {result.quality && (
            <SimpleGrid cols={{ base: 1, sm: 2 }}>
              <StatCard icon={<IconUsers size={24} />} label="Лиц без ИИН" value={`${result.quality.persons?.missing_iin_pct}%`} color="orange" />
              <StatCard icon={<IconDatabase size={24} />} label="Дел без меры" value={result.quality.admin_cases?.missing_measure} color="red" />
            </SimpleGrid>
          )}
        </>
      )}
    </Stack>
  );
}
