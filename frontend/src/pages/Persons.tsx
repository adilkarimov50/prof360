import { useEffect, useState } from "react";
import {
  Stack, Group, TextInput, Select, Table, Badge, Anchor, Paper, Text, Pagination,
} from "@mantine/core";
import { IconSearch } from "@tabler/icons-react";
import { Link } from "react-router-dom";
import api, { PersonShort, RISK_COLORS } from "../api";
import { useAuth } from "../auth";
import PageHeader from "../components/PageHeader";
import { PageLoader } from "../components/LoadingSkeleton";
import ErrorState from "../components/ErrorState";
import EmptyState from "../components/EmptyState";

const PAGE_SIZE = 50;

export default function Persons() {
  const { user } = useAuth();
  const [q, setQ] = useState("");
  const [risk, setRisk] = useState<string | null>(null);
  const [district, setDistrict] = useState<string | null>(user?.district || null);
  const [rows, setRows] = useState<PersonShort[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get<PersonShort[]>("/persons", {
        params: {
          q: q || undefined,
          risk: risk || undefined,
          district: district || undefined,
          limit: 200,
        },
      });
      setRows(data);
    } catch {
      setError("Не удалось загрузить список лиц");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);
  useEffect(() => {
    const t = setTimeout(() => { setPage(1); load(); }, 350);
    return () => clearTimeout(t);
  }, [q, risk, district]);

  const districts = [...new Set(rows.map((r) => r.district).filter(Boolean))] as string[];
  const paged = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <Stack>
      <PageHeader title="Лица и риск-профили" subtitle={`Найдено: ${rows.length}`} />
      <Group>
        <TextInput placeholder="Поиск по ФИО" leftSection={<IconSearch size={16} />} value={q} onChange={(e) => setQ(e.currentTarget.value)} w={320} />
        <Select placeholder="Уровень риска" clearable value={risk} onChange={setRisk} data={["Низкий", "Средний", "Высокий", "Критический"]} w={200} />
        {!user?.district && (
          <Select placeholder="Район" clearable searchable value={district} onChange={setDistrict} data={districts} w={240} />
        )}
      </Group>
      <Paper withBorder radius="md" p="md">
        {loading ? <PageLoader /> : error ? <ErrorState message={error} onRetry={load} /> : paged.length === 0 ? (
          <EmptyState />
        ) : (
          <>
            <Table highlightOnHover striped>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>ФИО</Table.Th>
                  <Table.Th>ИИН</Table.Th>
                  <Table.Th>Район</Table.Th>
                  <Table.Th>Балл</Table.Th>
                  <Table.Th>Уровень риска</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {paged.map((p) => (
                  <Table.Tr key={p.id}>
                    <Table.Td><Anchor component={Link} to={`/persons/${p.id}`} fw={500}>{p.fio}</Anchor></Table.Td>
                    <Table.Td><Text size="sm" c="dimmed" ff="monospace">{p.iin_masked}</Text></Table.Td>
                    <Table.Td>{p.district || "—"}</Table.Td>
                    <Table.Td>{p.risk_score}</Table.Td>
                    <Table.Td><Badge color={RISK_COLORS[p.risk_level] || "gray"}>{p.risk_level}</Badge></Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
            {rows.length > PAGE_SIZE && (
              <Group justify="center" mt="md">
                <Pagination total={Math.ceil(rows.length / PAGE_SIZE)} value={page} onChange={setPage} />
              </Group>
            )}
          </>
        )}
      </Paper>
    </Stack>
  );
}
