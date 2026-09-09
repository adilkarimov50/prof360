import { useEffect, useState } from "react";
import {
  Button, Card, Group, Select, Stack, Table, Text, TextInput, PasswordInput,
  Switch, SimpleGrid, Badge,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import api, { ROLE_LABELS } from "../api";
import PageHeader from "../components/PageHeader";
import { PageLoader } from "../components/LoadingSkeleton";
import ErrorState from "../components/ErrorState";

const ROLES = Object.keys(ROLE_LABELS);

export default function Admin() {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [form, setForm] = useState({
    username: "", full_name: "", password: "", role: "analyst",
    district: "", can_export: false, can_access_minors: false,
  });

  const load = () => {
    setLoading(true);
    setError("");
    api.get("/admin/ingestion-logs")
      .then((r) => setLogs(r.data))
      .catch(() => setError("Нет доступа или ошибка загрузки журнала"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const action = async (path: string, label: string) => {
    setBusy(path);
    try {
      const { data } = await api.post(path);
      notifications.show({ color: "teal", title: label, message: JSON.stringify(data) });
      load();
    } catch {
      notifications.show({ color: "red", title: "Ошибка", message: label });
    } finally {
      setBusy("");
    }
  };

  const createUser = async () => {
    setBusy("user");
    try {
      const { data } = await api.post("/admin/users", {
        ...form,
        district: form.district || null,
      });
      if (data.error) {
        notifications.show({ color: "red", title: "Ошибка", message: data.error });
      } else {
        notifications.show({ color: "teal", title: "Пользователь создан", message: data.username });
        setForm({ username: "", full_name: "", password: "", role: "analyst", district: "", can_export: false, can_access_minors: false });
      }
    } catch {
      notifications.show({ color: "red", title: "Не удалось создать пользователя", message: "Проверьте данные" });
    } finally {
      setBusy("");
    }
  };

  if (loading) return <PageLoader />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <Stack>
      <PageHeader title="Администрирование" subtitle="Пользователи, загрузки данных, пересчёт риска" />
      <SimpleGrid cols={{ base: 1, lg: 2 }}>
        <Card withBorder padding="lg">
          <Text fw={600} mb="md">Системные действия</Text>
          <Group>
            <Button loading={busy === "/admin/recompute-risk"} onClick={() => action("/admin/recompute-risk", "Риск пересчитан")}>
              Пересчитать риск
            </Button>
            <Button variant="light" loading={busy === "/admin/seed-legal"} onClick={() => action("/admin/seed-legal", "НПА обновлены")}>
              Seed НПА
            </Button>
            <Button variant="light" loading={busy === "/admin/seed-entitlements"} onClick={() => action("/admin/seed-entitlements", "Справочники обновлены")}>
              Seed МКБ/выплаты
            </Button>
            <Button variant="light" color="violet" loading={busy === "/admin/download-legal-docs"} onClick={() => action("/admin/download-legal-docs", "НПА скачаны и проиндексированы")}>
              Скачать все НПА с adilet
            </Button>
            <Button variant="light" color="violet" loading={busy === "/admin/ingest-codes"} onClick={() => action("/admin/ingest-codes", "Кодексы загружены с adilet")}>
              Индексировать нормы (ingest)
            </Button>
            <Button variant="light" color="teal" loading={busy === "/admin/import-registry-mkb"} onClick={() => action("/admin/import-registry-mkb", "МКБ импортированы")}>
              Импорт МКБ из реестра
            </Button>
            <Button variant="light" color="orange" loading={busy === "/admin/ingest"} onClick={() => action("/admin/ingest", "ETL выполнен")}>
              ETL из data_dir
            </Button>
          </Group>
        </Card>
        <Card withBorder padding="lg">
          <Text fw={600} mb="md">Новый пользователь</Text>
          <Stack gap="sm">
            <TextInput label="Логин" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
            <TextInput label="ФИО" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
            <PasswordInput label="Пароль" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            <Select label="Роль" data={ROLES.map((r) => ({ value: r, label: ROLE_LABELS[r] || r }))} value={form.role} onChange={(v) => setForm({ ...form, role: v || "analyst" })} />
            <TextInput label="Район (ABAC)" value={form.district} onChange={(e) => setForm({ ...form, district: e.target.value })} />
            <Switch label="Право экспорта" checked={form.can_export} onChange={(e) => setForm({ ...form, can_export: e.currentTarget.checked })} />
            <Switch label="Доступ к данным несовершеннолетних" checked={form.can_access_minors} onChange={(e) => setForm({ ...form, can_access_minors: e.currentTarget.checked })} />
            <Button loading={busy === "user"} onClick={createUser}>Создать</Button>
          </Stack>
        </Card>
      </SimpleGrid>
      <Card withBorder padding="lg">
        <Text fw={600} mb="md">Журнал загрузок Excel</Text>
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Дата</Table.Th>
              <Table.Th>Файл</Table.Th>
              <Table.Th>Всего</Table.Th>
              <Table.Th>Принято</Table.Th>
              <Table.Th>Отклонено</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {logs.map((l) => (
              <Table.Tr key={l.id}>
                <Table.Td>{l.ts ? new Date(l.ts).toLocaleString("ru-RU") : "—"}</Table.Td>
                <Table.Td>{l.file}</Table.Td>
                <Table.Td>{l.total}</Table.Td>
                <Table.Td><Badge color="teal">{l.accepted}</Badge></Table.Td>
                <Table.Td><Badge color="red">{l.rejected}</Badge></Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Card>
    </Stack>
  );
}
