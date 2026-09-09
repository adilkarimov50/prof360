import { useEffect, useState } from "react";
import { Badge, Card, Select, Stack, Table, Text } from "@mantine/core";
import api from "../api";
import PageHeader from "../components/PageHeader";
import { PageLoader } from "../components/LoadingSkeleton";
import ErrorState from "../components/ErrorState";
import EmptyState from "../components/EmptyState";

import type { AuditEvent, DlpExport } from "../types/api";

export default function Audit() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [dlp, setDlp] = useState<DlpExport[]>([]);
  const [action, setAction] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    setError("");
    Promise.all([
      api.get("/audit/events", { params: { action: action || undefined, limit: 200 } }),
      api.get("/audit/dlp/mass-exports"),
    ])
      .then(([ev, d]) => {
        setEvents(ev.data);
        setDlp(d.data);
      })
      .catch(() => setError("Нет доступа к журналу аудита"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [action]);

  if (loading) return <PageLoader />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <Stack>
      <PageHeader title="Аудит и DLP" subtitle="Журнал действий пользователей и массовые экспорты" />
      {dlp.length > 0 && (
        <Card withBorder padding="md">
          <Text fw={600} mb="sm" c="red">DLP: массовые экспорты</Text>
          <Table>
            <Table.Thead><Table.Tr><Table.Th>Пользователь</Table.Th><Table.Th>Экспортов</Table.Th><Table.Th>Порог</Table.Th></Table.Tr></Table.Thead>
            <Table.Tbody>
              {dlp.map((r) => (
                <Table.Tr key={r.username}>
                  <Table.Td>{r.username}</Table.Td>
                  <Table.Td><Badge color="red">{r.exports}</Badge></Table.Td>
                  <Table.Td>{r.threshold}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Card>
      )}
      <Card withBorder padding="lg">
        <Select
          label="Фильтр по действию"
          placeholder="Все действия"
          clearable
          mb="md"
          value={action}
          onChange={setAction}
          data={["login_success", "login_failed", "view_person", "export", "ai_chat", "ingest", "ingest_upload", "2fa_enabled"]}
        />
        {events.length === 0 ? <EmptyState message="Событий не найдено" /> : (
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Время</Table.Th>
                <Table.Th>Пользователь</Table.Th>
                <Table.Th>Действие</Table.Th>
                <Table.Th>Объект</Table.Th>
                <Table.Th>IP</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {events.map((e) => (
                <Table.Tr key={e.id}>
                  <Table.Td>{e.ts ? new Date(e.ts).toLocaleString("ru-RU") : "—"}</Table.Td>
                  <Table.Td>{e.username || "—"}</Table.Td>
                  <Table.Td><Badge variant="light">{e.action}</Badge></Table.Td>
                  <Table.Td>{e.entity_type ? `${e.entity_type} #${e.entity_id}` : "—"}</Table.Td>
                  <Table.Td>{e.ip || "—"}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Card>
    </Stack>
  );
}
