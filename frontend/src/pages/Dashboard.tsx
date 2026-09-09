import { useEffect, useState } from "react";
import {
  Tabs, SimpleGrid, Text, Group, Loader, Center, Table, Badge,
  Stack, Paper, ScrollArea, Anchor,
} from "@mantine/core";
import {
  IconUsers, IconAlertTriangle, IconGavel, IconShieldCheck, IconChartBar,
  IconBuildingCommunity, IconActivity, IconScale,
} from "@tabler/icons-react";
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import { Link } from "react-router-dom";
import api, { RISK_COLORS } from "../api";
import PageHeader from "../components/PageHeader";
import ErrorState from "../components/ErrorState";
import StatCard from "../components/StatCard";
import type { ChartClickPayload, DashboardOverview, ProceedingsData, TimeseriesPoint } from "../types/api";

const PALETTE = ["#4263eb", "#f59f00", "#e8590c", "#e03131", "#2f9e44", "#1098ad", "#9c36b5"];

interface SbData {
  sb_cases?: number;
  zp_violations?: number;
  protective_orders?: number;
  by_district?: { district: string; count: number }[];
}

interface OrganData {
  breakdown?: { series?: { line?: string; count?: number }[]; unknown?: number };
  mio?: { mio_preventive_records?: number; mio_persons?: number; mio_escalated_persons?: number; by_form?: { form: string; count: number }[] };
}

function districtClick(d: ChartClickPayload) {
  const district = d?.activePayload?.[0]?.payload?.district;
  if (district) window.location.assign(`/district/${encodeURIComponent(district)}`);
}

export default function Dashboard() {
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [timeseries, setTimeseries] = useState<TimeseriesPoint[]>([]);
  const [sb, setSb] = useState<SbData | null>(null);
  const [organs, setOrgans] = useState<OrganData | null>(null);
  const [proc, setProc] = useState<ProceedingsData & { total?: number; categories?: { code: string; title: string; count: number }[]; by_district?: { district: string; count: number }[]; cases?: Record<string, unknown>[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api.get("/dashboard/overview"),
      api.get("/dashboard/timeseries"),
      api.get("/dashboard/sb"),
      api.get("/dashboard/organs"),
      api.get("/dashboard/proceedings"),
    ])
      .then(([o, t, s, org, p]) => {
        setOverview(o.data);
        setTimeseries(t.data.series || []);
        setSb(s.data);
        setOrgans(org.data);
        setProc(p.data);
      })
      .catch(() => setError("Не удалось загрузить дашборд"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Center h="60vh"><Loader /></Center>;
  if (error) return <ErrorState message={error} />;

  const c = overview!.counters;

  return (
    <Stack>
      <PageHeader title="Аналитическая панель" />

      {(overview?.signals || []).length > 0 && overview && (
        <Paper withBorder radius="md" p="md">
          <Text fw={600} mb="sm">Сигналы системы</Text>
          <Group gap="xs">
            {overview.signals.map((s, i) => (
              <Badge key={i} color="red" variant="light">{s.type}: {s.count}</Badge>
            ))}
          </Group>
        </Paper>
      )}

      <Tabs defaultValue="overview" variant="pills" keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="overview" leftSection={<IconChartBar size={16} />}>
            Обзор
          </Tabs.Tab>
          <Tabs.Tab value="dynamics" leftSection={<IconActivity size={16} />}>
            Динамика
          </Tabs.Tab>
          <Tabs.Tab value="sb" leftSection={<IconShieldCheck size={16} />}>
            Семейно-бытовая
          </Tabs.Tab>
          <Tabs.Tab value="organs" leftSection={<IconBuildingCommunity size={16} />}>
            Полиция / МИО
          </Tabs.Tab>
          <Tabs.Tab value="proceedings" leftSection={<IconScale size={16} />}>
            Адм. производство
          </Tabs.Tab>
        </Tabs.List>

        {/* ===== Обзор ===== */}
        <Tabs.Panel value="overview">
          <Stack>
            <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
              <StatCard icon={<IconUsers size={24} />} label="Лиц на учёте" value={c.persons} color="indigo" />
              <StatCard icon={<IconAlertTriangle size={24} />} label="Высокий/крит. риск" value={c.high_risk} color="red" />
              <StatCard icon={<IconGavel size={24} />} label="Адм. дел" value={c.admin_cases} color="orange" />
              <StatCard icon={<IconShieldCheck size={24} />} label="Профучёт" value={c.preventive} color="teal" />
            </SimpleGrid>

            <SimpleGrid cols={{ base: 1, sm: 3 }}>
              <StatCard icon={<IconAlertTriangle size={24} />} label="Подлежат учёту" value={c.should_be_registered} color="yellow" />
              <StatCard icon={<IconActivity size={24} />} label="Повтор на учёте" value={c.repeat_on_register} color="grape" />
              <StatCard icon={<IconGavel size={24} />} label="Эскалация на учёте" value={c.escalation_during_register} color="red" />
            </SimpleGrid>

            <SimpleGrid cols={{ base: 1, lg: 2 }}>
              <Paper withBorder radius="md" p="md">
                <Text fw={600} mb="sm">Риск по районам (высокий + критический)</Text>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={(overview?.district_risk || []).slice(0, 10)} onClick={districtClick} style={{ cursor: "pointer" }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="district" tick={{ fontSize: 10 }} interval={0} angle={-25} textAnchor="end" height={70} />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="high" name="Высокий" stackId="a" fill="#f59f00" />
                    <Bar dataKey="critical" name="Критический" stackId="a" fill="#e03131" />
                  </BarChart>
                </ResponsiveContainer>
              </Paper>

              <Paper withBorder radius="md" p="md">
                <Text fw={600} mb="sm">Топ статей КоАП</Text>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={overview?.articles || []} layout="vertical" margin={{ left: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" />
                    <YAxis type="category" dataKey="article" tick={{ fontSize: 11 }} width={70} />
                    <Tooltip />
                    <Bar dataKey="count" name="Дел" fill="#4263eb" />
                  </BarChart>
                </ResponsiveContainer>
              </Paper>
            </SimpleGrid>

            <Paper withBorder radius="md" p="md">
              <Text fw={600} mb="sm">Лица наивысшего риска</Text>
              <ScrollArea>
                <Table highlightOnHover striped>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>ФИО</Table.Th>
                      <Table.Th>Район</Table.Th>
                      <Table.Th>Балл</Table.Th>
                      <Table.Th>Уровень</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {(overview?.top_persons || []).map((p) => (
                      <Table.Tr key={p.id}>
                        <Table.Td>
                          <Anchor component={Link} to={`/persons/${p.id}`}>{p.fio}</Anchor>
                        </Table.Td>
                        <Table.Td>{p.district || "—"}</Table.Td>
                        <Table.Td>{p.risk_score}</Table.Td>
                        <Table.Td>
                          <Badge color={RISK_COLORS[p.risk_level] || "gray"}>{p.risk_level}</Badge>
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </ScrollArea>
            </Paper>
          </Stack>
        </Tabs.Panel>

        {/* ===== Динамика ===== */}
        <Tabs.Panel value="dynamics">
          <Paper withBorder radius="md" p="md">
            <Text fw={600} mb="sm">Динамика административных дел по месяцам</Text>
            <ResponsiveContainer width="100%" height={400}>
              <LineChart data={timeseries}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="count" name="Дел" stroke="#4263eb" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </Paper>
        </Tabs.Panel>

        {/* ===== Семейно-бытовая ===== */}
        <Tabs.Panel value="sb">
          <Stack>
            <SimpleGrid cols={{ base: 1, sm: 3 }}>
              <StatCard icon={<IconShieldCheck size={24} />} label="Дел ст.73 (семейно-бытовые)" value={sb?.sb_cases} color="orange" />
              <StatCard icon={<IconAlertTriangle size={24} />} label="Нарушения ЗП (ст.461)" value={sb?.zp_violations} color="red" />
              <StatCard icon={<IconGavel size={24} />} label="Защитные предписания" value={sb?.protective_orders} color="teal" />
            </SimpleGrid>
            <Paper withBorder radius="md" p="md">
              <Text fw={600} mb="sm">Семейно-бытовые правонарушения по районам</Text>
              <ResponsiveContainer width="100%" height={350}>
                <BarChart data={sb?.by_district || []} onClick={districtClick} style={{ cursor: "pointer" }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="district" tick={{ fontSize: 10 }} interval={0} angle={-25} textAnchor="end" height={80} />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="count" name="Дел" fill="#e8590c" />
                </BarChart>
              </ResponsiveContainer>
            </Paper>
          </Stack>
        </Tabs.Panel>

        {/* ===== Полиция / МИО ===== */}
        <Tabs.Panel value="organs">
          <SimpleGrid cols={{ base: 1, lg: 2 }}>
            <Paper withBorder radius="md" p="md">
              <Text fw={600} mb="sm">Разрез по линиям ответственности</Text>
              <ResponsiveContainer width="100%" height={320}>
                <PieChart>
                  <Pie
                    data={organs?.breakdown?.series || []}
                    dataKey="count"
                    nameKey="line"
                    cx="50%"
                    cy="50%"
                    outerRadius={110}
                    label
                  >
                    {(organs?.breakdown?.series || []).map((_, i) => (
                      <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </Paper>
            <Stack>
              <SimpleGrid cols={2}>
                <StatCard icon={<IconShieldCheck size={24} />} label="Записи профучёта МИО" value={organs?.mio?.mio_preventive_records} color="teal" />
                <StatCard icon={<IconUsers size={24} />} label="Лиц в зоне МИО" value={organs?.mio?.mio_persons} color="indigo" />
                <StatCard icon={<IconAlertTriangle size={24} />} label="Эскалация (зона МИО)" value={organs?.mio?.mio_escalated_persons} color="red" />
                <StatCard icon={<IconBuildingCommunity size={24} />} label="Не распознано" value={organs?.breakdown?.unknown} color="gray" />
              </SimpleGrid>
              <Paper withBorder radius="md" p="md">
                <Text fw={600} mb="sm">Профучёт МИО по формам</Text>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={organs?.mio?.by_form || []}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="form" tick={{ fontSize: 10 }} />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="count" name="Записей" fill="#1098ad" />
                  </BarChart>
                </ResponsiveContainer>
              </Paper>
            </Stack>
          </SimpleGrid>
        </Tabs.Panel>

        {/* ===== Адм. производство ===== */}
        <Tabs.Panel value="proceedings">
          <Stack>
            <Group>
              <Badge size="lg" color="red" variant="filled">
                Кандидатов на проверку: {proc?.total ?? 0}
              </Badge>
            </Group>
            <SimpleGrid cols={{ base: 1, lg: 2 }}>
              <Paper withBorder radius="md" p="md">
                <Text fw={600} mb="sm">Категории нарушений законности</Text>
                <ResponsiveContainer width="100%" height={320}>
                  <BarChart data={proc?.categories || []} layout="vertical" margin={{ left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" />
                    <YAxis type="category" dataKey="code" tick={{ fontSize: 10 }} width={110} />
                    <Tooltip formatter={(v, _n, p) => [v, (p?.payload as { title?: string })?.title]} />
                    <Bar dataKey="count" name="Дел" fill="#e03131" />
                  </BarChart>
                </ResponsiveContainer>
              </Paper>
              <Paper withBorder radius="md" p="md">
                <Text fw={600} mb="sm">По районам</Text>
                <ResponsiveContainer width="100%" height={320}>
                  <BarChart data={proc?.by_district || []}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="district" tick={{ fontSize: 10 }} interval={0} angle={-25} textAnchor="end" height={80} />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="count" name="Дел" fill="#f59f00" />
                  </BarChart>
                </ResponsiveContainer>
              </Paper>
            </SimpleGrid>

            <Paper withBorder radius="md" p="md">
              <Text fw={600} mb="sm">Реестр дел — кандидатов на проверку</Text>
              <ScrollArea h={400}>
                <Table highlightOnHover striped stickyHeader>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Материал</Table.Th>
                      <Table.Th>Дата</Table.Th>
                      <Table.Th>ФИО</Table.Th>
                      <Table.Th>Квалификация</Table.Th>
                      <Table.Th>Решение</Table.Th>
                      <Table.Th>Признак</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {(proc?.cases || []).map((row) => {
                      const r = row as Record<string, string | number>;
                      return (
                      <Table.Tr key={String(r.case_id)}>
                        <Table.Td>{r.material_no || "—"}</Table.Td>
                        <Table.Td>{r.case_date || "—"}</Table.Td>
                        <Table.Td>
                          <Anchor component={Link} to={`/persons/${r.person_id}`}>{r.fio}</Anchor>
                        </Table.Td>
                        <Table.Td>{r.qualification || "—"}</Table.Td>
                        <Table.Td>{r.decision || "—"}</Table.Td>
                        <Table.Td>
                          <Badge color="red" variant="light" size="sm">{r.violation}</Badge>
                        </Table.Td>
                      </Table.Tr>
                    );})}
                  </Table.Tbody>
                </Table>
              </ScrollArea>
            </Paper>
          </Stack>
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
