import { useEffect, useState } from "react";
import {
  Alert,
  Badge,
  Card,
  Group,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import {
  IconAlertTriangle,
  IconChartBar,
  IconDeviceMobile,
  IconGavel,
  IconShield,
  IconUsers,
} from "@tabler/icons-react";
import api from "../api";
import PageHeader from "../components/PageHeader";
import StatCard from "../components/StatCard";
import { PageLoader } from "../components/LoadingSkeleton";
import ErrorState from "../components/ErrorState";

const TOPIC_LABELS = [
  { key: "cyber_fraud", label: "Интернет-мошенничество (ЕРДР)", icon: <IconDeviceMobile size={24} />, color: "red" },
  { key: "extortion", label: "Вымогательство", icon: <IconGavel size={24} />, color: "orange" },
  { key: "vape_violations", label: "Незаконный оборот вейпов (ст.301-1)", icon: <IconShield size={24} />, color: "pink" },
  { key: "alcohol_admin_cases", label: "Алкогольные адм. правонарушения", icon: <IconAlertTriangle size={24} />, color: "yellow" },
  { key: "alcohol_intoxicated_offenders", label: "Нарушители в состоянии опьянения", icon: <IconAlertTriangle size={24} />, color: "yellow" },
  { key: "juvenile_preventive_records", label: "Несовершеннолетние на профучёте", icon: <IconUsers size={24} />, color: "grape" },
];

const PRIORITY_CONTEXT = [
  { label: "Интернет-мошенничество 2025 (область)", value: "1 711 фактов", change: "+16,4% к 2024", color: "red" },
  { label: "Интернет-мошенничество янв. 2026", value: "71 факт", change: "-25,3% к янв. 2025", color: "teal" },
  { label: "Вымогательство 2025", value: "45 уг. дел", change: "+55,2%", color: "orange" },
  { label: "Вымогательство янв. 2026", value: "2 уг. дела", change: "-75,0%", color: "teal" },
  { label: "Преступления несовершеннолетними 2025", value: "125", change: "+31,6%", color: "red" },
  { label: "Преступления против несовершеннолетних 2025", value: "336", change: "-13,1%", color: "teal" },
  { label: "Вейп (ст.301-1) возбуждено 2025", value: "4 уг. дела", change: "+действует с 20.06.2024", color: "pink" },
  { label: "Мас күйінде жасалған қылмыс 2025", value: "604", change: "7,1% от всех", color: "orange" },
];

const CYBER_DISTRICT_2025 = [
  { district: "Талгарский", count: 452, change: "+13,6%" },
  { district: "Карасайский", count: 276, change: "-14,0%" },
  { district: "Илийский", count: 261, change: "+49,1%" },
  { district: "Енбекшиказахский", count: 335, change: "+26,4%" },
  { district: "Жамбылский", count: 167, change: "-9,7%" },
  { district: "Конаев", count: 118, change: "+4,4р." },
  { district: "Алатауский", count: 41, change: "+10,8%" },
  { district: "Уйгурский", count: 46, change: "+9,5%" },
  { district: "Балхашский", count: 7, change: "-36,4%" },
  { district: "Кегенский", count: 3, change: "+50,0%" },
  { district: "Райымбекский", count: 5, change: "-28,6%" },
];

export default function CommissionAnalytics() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/analytics/commission-stats")
      .then((r) => { setStats(r.data); setError(""); })
      .catch(() => setError("Не удалось загрузить статистику"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <PageLoader />;
  if (error && !stats) return <ErrorState message={error} />;

  return (
    <Stack gap="md">
      <PageHeader
        title="Аналитика МВК по профилактике"
        subtitle="Статистика по темам Межведомственной комиссии: интернет-мошенничество, вымогательство, несовершеннолетние, алкоголь, вейп"
      />

      <Alert color="blue" title="Источники данных">
        Данные из системы «Профилактика 360» (ЕРДР/профучёт). Статистика МВК из реальных протоколов приведена
        отдельно в блоке «Справочно по протоколам МВК 2026».
      </Alert>

      <Card withBorder padding="lg">
        <Text fw={600} mb="md">Из базы данных системы</Text>
        <SimpleGrid cols={{ base: 2, sm: 3, md: 3 }}>
          {TOPIC_LABELS.map((t) => (
            <StatCard
              key={t.key}
              icon={t.icon}
              label={t.label}
              value={stats?.[t.key] ?? "—"}
              color={t.color}
            />
          ))}
        </SimpleGrid>
      </Card>

      <Card withBorder padding="lg">
        <Text fw={600} mb="md">Справочно по протоколам МВК 2026 (реальные данные ПД/ДСБ/УО)</Text>
        <SimpleGrid cols={{ base: 1, sm: 2, md: 4 }}>
          {PRIORITY_CONTEXT.map((item) => (
            <Card key={item.label} withBorder padding="sm" radius="md">
              <Text size="xs" c="dimmed">{item.label}</Text>
              <Group gap="xs" align="baseline">
                <Text fw={700} size="lg">{item.value}</Text>
                <Badge size="sm" color={item.color}>{item.change}</Badge>
              </Group>
            </Card>
          ))}
        </SimpleGrid>
      </Card>

      <Card withBorder padding="lg">
        <Group mb="md">
          <IconChartBar size={20} />
          <Text fw={600}>Интернет-мошенничество по районам — 2025 год (из протоколов МВК)</Text>
        </Group>
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Район / город</Table.Th>
              <Table.Th>Количество 2025</Table.Th>
              <Table.Th>Динамика</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {CYBER_DISTRICT_2025.sort((a, b) => b.count - a.count).map((r) => (
              <Table.Tr key={r.district}>
                <Table.Td>{r.district}</Table.Td>
                <Table.Td><Text fw={600}>{r.count}</Text></Table.Td>
                <Table.Td>
                  <Badge color={r.change.startsWith("-") ? "teal" : "red"} variant="light">
                    {r.change}
                  </Badge>
                </Table.Td>
              </Table.Tr>
            ))}
            <Table.Tr>
              <Table.Td><Text fw={700}>ИТОГО</Text></Table.Td>
              <Table.Td><Text fw={700}>1 711</Text></Table.Td>
              <Table.Td><Badge color="red" variant="light">+16,4%</Badge></Table.Td>
            </Table.Tr>
          </Table.Tbody>
        </Table>
      </Card>

      <Card withBorder padding="lg">
        <Title order={5} mb="md">Приоритеты для прокурорского надзора по итогам МВК</Title>
        <Stack gap="xs">
          {[
            { label: "Карасайский район", issue: "Вымогательство +14,5 раза в 2025; преступность несовершеннолетних +4,7 раза", color: "red" },
            { label: "Талгарский район", issue: "Интернет-мошенничество 452 факта; несовершеннолетние +80%; преступления против н/л 82 факта", color: "red" },
            { label: "Илийский район", issue: "Интернет-мошенничество +49,1%; в янв. 2026 +38,5%", color: "orange" },
            { label: "Енбекшиказахский район", issue: "Интернет-мошенничество +26,4%; несовершеннолетних на профучёте больше всего", color: "orange" },
            { label: "Конаев г.", issue: "Интернет-мошенничество в янв. 2026 +42,9%; нехватка УБДБ", color: "yellow" },
            { label: "Жамбылский район", issue: "Убийства несовершеннолетними в начале 2026 года (2 случая)", color: "red" },
          ].map((item) => (
            <Alert key={item.label} color={item.color} title={item.label} variant="light">
              {item.issue}
            </Alert>
          ))}
        </Stack>
      </Card>
    </Stack>
  );
}
