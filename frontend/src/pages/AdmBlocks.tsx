import { useEffect, useState } from "react";
import {
  Title, Stack, Card, Text, Group, SimpleGrid, Table, Badge, Alert, Loader,
  Button, ThemeIcon, Divider, Progress, List,
} from "@mantine/core";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import {
  IconAlertTriangle, IconCar, IconUsers, IconDownload, IconGavel, IconScale,
} from "@tabler/icons-react";
import { notifications } from "@mantine/notifications";
import api from "../api";
import { useAuth } from "../auth";

interface ArticleRow {
  article: string;
  title: string;
  count: number;
  share_pct: number;
}

interface GroupRow {
  name: string;
  count: number;
  share_pct: number;
}

interface EnforcementRow {
  article: string;
  title: string;
  total: number;
  fine: number;
  strict: number;
  warning: number;
  terminated: number;
  real_pct: number;
  warning_pct: number;
  terminated_pct: number;
}

interface Outcome {
  fine: number;
  strict: number;
  warning: number;
  terminated: number;
  real_penalty: number;
  real_pct: number;
  warning_pct: number;
}

interface UnitRow {
  unit: string;
  total: number;
  person: number;
  road: number;
  other: number;
  person_pct: number;
}

interface BlockStats {
  block: string;
  label: string;
  total: number;
  articles: ArticleRow[];
  groups: GroupRow[];
  by_month: Record<string, number>;
  measures: { name: string; count: number }[];
  sex: { name: string; count: number }[];
  age: { name: string; count: number }[];
  terminated: number;
  terminated_pct: number;
  imposed: number;
  fines_total: number;
}

interface Analysis {
  locality: string;
  period: string;
  total: number;
  blocks: Record<"person" | "road" | "other", BlockStats>;
  outcomes: Record<"person" | "road" | "other", Outcome>;
  enforcement_person: EnforcementRow[];
  enforcement_road: EnforcementRow[];
  unit_load: UnitRow[];
  ratio_road_to_person: number;
  person_share_pct: number;
  road_share_pct: number;
}

const MONTHS: Record<string, string> = {
  "2026-01": "янв", "2026-02": "фев", "2026-03": "мар", "2026-04": "апр",
  "2026-05": "май", "2026-06": "июн", "2026-07": "июл", "2026-08": "авг",
};

const fmt = (n: number) => n.toLocaleString("ru-RU");

export default function AdmBlocks() {
  const { user } = useAuth();
  const [data, setData] = useState<Analysis | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .get("/reports/adm-blocks")
      .then((r) => setData(r.data))
      .catch(() => setError("Не удалось загрузить аналитику формы 1-АД"));
  }, []);

  const download = async () => {
    setBusy(true);
    try {
      const resp = await api.post(
        "/reports/generate",
        { kind: "adm_blocks", format: "docx" },
        { responseType: "blob" },
      );
      const cd = resp.headers["content-disposition"] || "";
      const m = /filename="?([^"]+)"?/.exec(cd);
      const fname = m ? m[1] : "adm_blocks.docx";
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = fname;
      a.click();
      URL.revokeObjectURL(url);
      notifications.show({ color: "teal", title: "Готово", message: fname });
    } catch {
      notifications.show({
        color: "red",
        title: "Ошибка",
        message: "Не удалось сформировать документ",
      });
    } finally {
      setBusy(false);
    }
  };

  if (error) {
    return (
      <Alert color="red" variant="light" icon={<IconAlertTriangle size={16} />}>
        {error}
      </Alert>
    );
  }
  if (!data) {
    return (
      <Group justify="center" mt="xl">
        <Loader />
      </Group>
    );
  }

  const { person, road, other } = data.blocks;
  const po = data.outcomes.person;
  const ro = data.outcomes.road;

  const monthly = Object.keys(person.by_month).map((k) => ({
    month: MONTHS[k] || k,
    "Против личности и общества": person.by_month[k] || 0,
    "Дорожная безопасность": road.by_month[k] || 0,
  }));

  const art440 = data.enforcement_person.find((e) => e.article === "ст.440");
  const art73 = data.enforcement_person.find((e) => e.article === "ст.73");

  const blockCards = [
    {
      st: person,
      out: po,
      color: "red",
      icon: IconUsers,
      hint: "ст. 73, 127, 434, 437, 440, 442, 449, 480 КоАП",
    },
    {
      st: road,
      out: ro,
      color: "blue",
      icon: IconCar,
      hint: "глава 30 КоАП, ст. 230 (ОСАГО)",
    },
    {
      st: other,
      out: data.outcomes.other,
      color: "gray",
      icon: IconGavel,
      hint: "миграция, благоустройство, торговля, оружие и иные",
    },
  ];

  const articleTable = (rows: ArticleRow[]) => (
    <Table striped highlightOnHover withTableBorder>
      <Table.Thead>
        <Table.Tr>
          <Table.Th w={90}>Статья</Table.Th>
          <Table.Th>Содержание</Table.Th>
          <Table.Th w={60}>Дел</Table.Th>
          <Table.Th w={80}>Доля</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {rows.map((a) => (
          <Table.Tr key={a.article}>
            <Table.Td>
              <Text fw={600} size="sm">{a.article}</Text>
            </Table.Td>
            <Table.Td>
              <Text size="sm">{a.title}</Text>
            </Table.Td>
            <Table.Td>{a.count}</Table.Td>
            <Table.Td>
              <Text size="sm" c="dimmed">{a.share_pct} %</Text>
            </Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );

  const enforcementTable = (rows: EnforcementRow[]) => (
    <Table striped highlightOnHover withTableBorder>
      <Table.Thead>
        <Table.Tr>
          <Table.Th w={90}>Статья</Table.Th>
          <Table.Th>Содержание</Table.Th>
          <Table.Th w={55}>Дел</Table.Th>
          <Table.Th w={70}>Штраф</Table.Th>
          <Table.Th w={70}>Арест</Table.Th>
          <Table.Th w={100}>Предупр.</Table.Th>
          <Table.Th w={110}>Прекращено</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {rows.map((e) => (
          <Table.Tr key={e.article}>
            <Table.Td>
              <Text fw={600} size="sm">{e.article}</Text>
            </Table.Td>
            <Table.Td>
              <Text size="sm">{e.title}</Text>
            </Table.Td>
            <Table.Td>{e.total}</Table.Td>
            <Table.Td>{e.fine}</Table.Td>
            <Table.Td>{e.strict}</Table.Td>
            <Table.Td>
              <Text size="sm" c={e.warning_pct > 80 ? "orange" : undefined} fw={e.warning_pct > 80 ? 600 : 400}>
                {e.warning} ({e.warning_pct} %)
              </Text>
            </Table.Td>
            <Table.Td>
              <Text size="sm" c={e.terminated_pct > 20 ? "red" : undefined} fw={e.terminated_pct > 20 ? 600 : 400}>
                {e.terminated} ({e.terminated_pct} %)
              </Text>
            </Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );

  return (
    <Stack>
      <Group justify="space-between" align="flex-start">
        <Stack gap={2}>
          <Title order={2}>Административная практика: личность и общество vs дорожная безопасность</Title>
          <Text size="sm" c="dimmed">
            {data.locality} · {data.period} · форма 1-АД · всего {fmt(data.total)} производств
          </Text>
        </Stack>
        <Button
          leftSection={<IconDownload size={16} />}
          loading={busy}
          disabled={!user?.can_export}
          onClick={download}
        >
          Справка в Word
        </Button>
      </Group>

      <Alert color="red" variant="light" icon={<IconAlertTriangle size={18} />} title="Ключевые выводы">
        <List size="sm" spacing={4}>
          <List.Item>
            На одно производство по составам против личности и общества приходится{" "}
            <b>{data.ratio_road_to_person}</b> производства по дорожной безопасности.
          </List.Item>
          {art440 && (
            <List.Item>
              По ст. 440 КоАП (алкоголь в общественных местах) прекращено{" "}
              <b>{art440.terminated} из {art440.total}</b> дел ({art440.terminated_pct} %) — максимум по массиву.
            </List.Item>
          )}
          {art73 && (
            <List.Item>
              По ст. 73 КоАП (семейно-бытовая сфера) за период — всего <b>{art73.total} протоколов</b>,
              из них {art73.terminated} прекращено; штраф не назначался ни разу.
            </List.Item>
          )}
          <List.Item>
            Предупреждением завершились <b>{po.warning} из {person.total}</b> «личных» дел
            ({po.warning_pct} %); реальное взыскание — {po.real_pct} % против {ro.real_pct} % в дорожном блоке.
          </List.Item>
        </List>
      </Alert>

      <SimpleGrid cols={{ base: 1, md: 3 }}>
        {blockCards.map(({ st, out, color, icon: Icon, hint }) => (
          <Card key={st.block} withBorder radius="md" padding="lg">
            <Group justify="space-between" mb="sm">
              <ThemeIcon size={42} radius="md" variant="light" color={color}>
                <Icon size={22} />
              </ThemeIcon>
              <Badge variant="light" color={color}>
                {((st.total / data.total) * 100).toFixed(1)} %
              </Badge>
            </Group>
            <Text fw={600}>{st.label}</Text>
            <Text size="xs" c="dimmed" mb="sm">{hint}</Text>
            <Text fz={30} fw={700}>{fmt(st.total)}</Text>
            <Divider my="sm" />
            <Group justify="space-between">
              <Text size="sm" c="dimmed">Реальное взыскание</Text>
              <Text size="sm" fw={600}>{out.real_penalty} ({out.real_pct} %)</Text>
            </Group>
            <Group justify="space-between">
              <Text size="sm" c="dimmed">Предупреждение</Text>
              <Text size="sm" fw={600} c={out.warning_pct > 50 ? "orange" : undefined}>
                {out.warning} ({out.warning_pct} %)
              </Text>
            </Group>
            <Group justify="space-between">
              <Text size="sm" c="dimmed">Прекращено</Text>
              <Text size="sm" fw={600} c={st.terminated_pct > 15 ? "red" : undefined}>
                {st.terminated} ({st.terminated_pct} %)
              </Text>
            </Group>
            <Group justify="space-between">
              <Text size="sm" c="dimmed">Штрафы, тг</Text>
              <Text size="sm" fw={600}>{fmt(st.fines_total)}</Text>
            </Group>
          </Card>
        ))}
      </SimpleGrid>

      <Card withBorder radius="md" padding="lg">
        <Text fw={600} mb="md">Динамика по месяцам</Text>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={monthly}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="month" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="Против личности и общества" fill="#e03131" radius={[4, 4, 0, 0]} />
            <Bar dataKey="Дорожная безопасность" fill="#4263eb" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <Card withBorder radius="md" padding="lg">
        <Text fw={600} mb="md">Направления блока «против личности и общества»</Text>
        <Stack gap="sm">
          {person.groups.map((g) => (
            <div key={g.name}>
              <Group justify="space-between" mb={4}>
                <Text size="sm">{g.name}</Text>
                <Text size="sm" fw={600}>{g.count} ({g.share_pct} %)</Text>
              </Group>
              <Progress value={g.share_pct} color="red" size="sm" radius="xl" />
            </div>
          ))}
        </Stack>
      </Card>

      <SimpleGrid cols={{ base: 1, lg: 2 }}>
        <Card withBorder radius="md" padding="lg">
          <Group mb="md">
            <ThemeIcon variant="light" color="red"><IconUsers size={18} /></ThemeIcon>
            <Text fw={600}>Против личности и общества</Text>
          </Group>
          {articleTable(person.articles)}
        </Card>
        <Card withBorder radius="md" padding="lg">
          <Group mb="md">
            <ThemeIcon variant="light" color="blue"><IconCar size={18} /></ThemeIcon>
            <Text fw={600}>Дорожная безопасность</Text>
          </Group>
          {articleTable(road.articles)}
        </Card>
      </SimpleGrid>

      <Card withBorder radius="md" padding="lg">
        <Group mb="xs">
          <ThemeIcon variant="light" color="red"><IconScale size={18} /></ThemeIcon>
          <Text fw={600}>Фактические исходы: против личности и общества</Text>
        </Group>
        <Text size="sm" c="dimmed" mb="md">
          Исход определяется по решению по делу: записи «исполнение наказания: погашение штрафа»
          означают наложенный и погашенный штраф, а не отсутствие меры взыскания.
        </Text>
        {enforcementTable(data.enforcement_person)}
      </Card>

      <Card withBorder radius="md" padding="lg">
        <Group mb="md">
          <ThemeIcon variant="light" color="blue"><IconScale size={18} /></ThemeIcon>
          <Text fw={600}>Фактические исходы: дорожная безопасность</Text>
        </Group>
        {enforcementTable(data.enforcement_road.slice(0, 10))}
      </Card>

      <Card withBorder radius="md" padding="lg">
        <Text fw={600} mb="md">Нагрузка подразделений ОВД по блокам</Text>
        <Table striped highlightOnHover withTableBorder>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Подразделение</Table.Th>
              <Table.Th w={90}>Всего</Table.Th>
              <Table.Th w={130}>Личность</Table.Th>
              <Table.Th w={130}>Дороги</Table.Th>
              <Table.Th w={100}>Иные</Table.Th>
              <Table.Th w={110}>Доля личности</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {data.unit_load.map((u) => (
              <Table.Tr key={u.unit}>
                <Table.Td><Text size="sm">{u.unit}</Text></Table.Td>
                <Table.Td>{fmt(u.total)}</Table.Td>
                <Table.Td>{u.person}</Table.Td>
                <Table.Td>{u.road}</Table.Td>
                <Table.Td>{u.other}</Table.Td>
                <Table.Td>
                  <Text size="sm" c={u.person_pct < 20 ? "orange" : undefined}>{u.person_pct} %</Text>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        <Text size="sm" c="dimmed" mt="md">
          Портрет привлечённого лица в «личном» блоке:{" "}
          {person.sex.map((s) => `${s.name} — ${s.count}`).join(", ")}. Преобладающая возрастная
          группа — {person.age[0]?.name} ({person.age[0]?.count}).
        </Text>
      </Card>

      <Alert color="indigo" variant="light" icon={<IconGavel size={18} />} title="Правовая основа рекомендаций">
        Приказ Генерального Прокурора РК от 17.01.2023 № 32: п. 27 Приложения 1 — проверки
        законности производства по делам об АП; п. 38–40, 44 Приложения 1 — порядок и источники
        анализа состояния законности; п. 24, 25 Приложения 1 — профилактика правонарушений как
        обязательный предмет проверки и содержание справки; п. 27, 29, 36 Приложения 3 — участие
        прокурора, суточная проверка постановлений об аресте, реагирование на прекращение
        производства; п. 5, 6, 15 Приложения 2 — требования к актам надзора и паспорт региона.
        Полный текст рекомендаций — в справке Word.
      </Alert>
    </Stack>
  );
}
