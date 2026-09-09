import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  Title, Stack, Group, Card, Text, Badge, RingProgress, SimpleGrid, Table, Tabs,
  Loader, Center, Timeline, List, Button, Paper, Menu, Anchor, ThemeIcon, Alert,
} from "@mantine/core";
import { IconRobot, IconArrowLeft, IconFileDownload, IconGavel, IconShieldCheck, IconAlertTriangle,
  IconClockHour4, IconChevronDown, IconUserExclamation, IconStethoscope, IconExternalLink,
} from "@tabler/icons-react";
import type { PersonSupportPayload } from "../types/api";
import { notifications } from "@mantine/notifications";
import api, { RISK_COLORS } from "../api";
import { useAuth } from "../auth";

const RING_COLOR: Record<string, string> = {
  Низкий: "green",
  Средний: "yellow",
  Высокий: "orange",
  Критический: "red",
};

const ACTS = [
  { kind: "representation", label: "Представление об устранении нарушений" },
  { kind: "protest", label: "Протест (незаконный адм. материал)" },
  { kind: "appeal", label: "Апелляционное ходатайство" },
  { kind: "requirement", label: "Требование прокурора" },
];

export default function PersonCard() {
  const { id } = useParams();
  const { user } = useAuth();
  const [p, setP] = useState<any>(null);
  const [measures, setMeasures] = useState<any[]>([]);
  const [support, setSupport] = useState<PersonSupportPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.get(`/persons/${id}`),
      api.get(`/persons/${id}/measures`),
      api.get<PersonSupportPayload>(`/persons/${id}/support`).catch(() => ({ data: null })),
    ])
      .then(([d, m, s]) => {
        setP(d.data);
        setMeasures(m.data.measures || []);
        setSupport(s.data);
      })
      .finally(() => setLoading(false));
  }, [id]);

  const download = async (kind: string, caseId?: number) => {
    setBusy(kind + (caseId || ""));
    try {
      const resp = await api.post(
        "/reports/generate",
        { kind, target: String(id), case_id: caseId },
        { responseType: "blob" }
      );
      const cd = resp.headers["content-disposition"] || "";
      const m = /filename="?([^"]+)"?/.exec(cd);
      const fname = m ? m[1] : `${kind}.docx`;
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = fname;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      notifications.show({
        color: "red",
        title: "Не удалось сформировать документ",
        message: e?.response?.status === 403 ? "Недостаточно прав (экспорт)" : "Ошибка генерации",
      });
    } finally {
      setBusy("");
    }
  };

  if (loading)
    return (
      <Center h="60vh">
        <Loader />
      </Center>
    );
  if (!p) return <Text>Лицо не найдено</Text>;

  return (
    <Stack>
      <Group justify="space-between">
        <Group>
        <Button component={Link} to="/persons" variant="subtle" leftSection={<IconArrowLeft size={16} />}>
          К списку
        </Button>
        <Button component={Link} to={`/ai?context_type=person&context_id=${id}&q=${encodeURIComponent(`Проанализируй риск-профиль и рекомендуемые меры по лицу ${p.fio}`)}`} variant="light" leftSection={<IconRobot size={16} />}>
          Спросить ИИ
        </Button>
        {user?.can_export ? (
          <Menu shadow="md" width={320}>
            <Menu.Target>
              <Button leftSection={<IconFileDownload size={16} />} rightSection={<IconChevronDown size={14} />}>
                Сформировать документ
              </Button>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Label>Аналитическая справка</Menu.Label>
              <Menu.Item onClick={() => download("person")} disabled={busy === "person"}>
                Справка по лицу (риск-профиль)
              </Menu.Item>
              <Menu.Label>Акты реагирования (Приказ ГП РК №32)</Menu.Label>
              {ACTS.map((a) => (
                <Menu.Item key={a.kind} onClick={() => download(a.kind)} disabled={busy === a.kind}>
                  {a.label}
                </Menu.Item>
              ))}
            </Menu.Dropdown>
          </Menu>
        ) : (
          <Badge color="gray" variant="light">Нет права экспорта</Badge>
        )}
        </Group>
      </Group>

      <Card withBorder radius="md" padding="lg">
        <Group justify="space-between" wrap="nowrap">
          <div>
            <Title order={3}>{p.fio}</Title>
            <Text c="dimmed" ff="monospace">
              ИИН {p.iin_masked}
            </Text>
            <Group mt="xs" gap="xs">
              <Badge variant="light">{p.district || "Район не указан"}</Badge>
              {p.locality && <Badge variant="light" color="gray">{p.locality}</Badge>}
              {p.birth_date && <Badge variant="light" color="gray">{p.birth_date}</Badge>}
              {p.gender && <Badge variant="light" color="gray">{p.gender}</Badge>}
            </Group>
          </div>
          <RingProgress
            size={120}
            thickness={12}
            roundCaps
            sections={[{ value: Math.min(100, p.risk_score), color: RING_COLOR[p.risk_level] || "gray" }]}
            label={
              <div style={{ textAlign: "center" }}>
                <Text fw={700} size="lg">{p.risk_score}</Text>
                <Badge size="sm" color={RISK_COLORS[p.risk_level] || "gray"}>{p.risk_level}</Badge>
              </div>
            }
          />
        </Group>
      </Card>

      {p.signals?.length > 0 && (
        <Alert color="red" variant="light" icon={<IconAlertTriangle size={18} />} title="Автоматические сигналы">
          <List spacing={4} size="sm">
            {p.signals.map((s: any, i: number) => (
              <List.Item key={i}>
                <Badge size="xs" color="red" mr={6}>{s.level}</Badge>
                {s.message}
              </List.Item>
            ))}
          </List>
        </Alert>
      )}

      <Tabs defaultValue="timeline" variant="outline">
        <Tabs.List mb="md">
          <Tabs.Tab value="timeline" leftSection={<IconClockHour4 size={16} />}>Хронология</Tabs.Tab>
          <Tabs.Tab value="factors" leftSection={<IconAlertTriangle size={16} />}>Риск-факторы</Tabs.Tab>
          <Tabs.Tab value="admin" leftSection={<IconGavel size={16} />}>Адм. дела ({p.admin_cases?.length || 0})</Tabs.Tab>
          <Tabs.Tab value="preventive" leftSection={<IconShieldCheck size={16} />}>Профучёт ({p.preventive_records?.length || 0})</Tabs.Tab>
          <Tabs.Tab value="suspects" leftSection={<IconUserExclamation size={16} />}>Подозрения ({p.suspects?.length || 0})</Tabs.Tab>
          <Tabs.Tab value="support" leftSection={<IconStethoscope size={16} />}>
            МКБ и поддержка{support?.icd_codes?.length ? ` (${support.icd_codes.length})` : ""}
          </Tabs.Tab>
          <Tabs.Tab value="measures">Меры (Приказ №32)</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="timeline">
          <Paper withBorder radius="md" p="lg">
            {p.timeline?.length ? (
              <Timeline active={p.timeline.length} bulletSize={22} lineWidth={2}>
                {p.timeline.map((e: any, i: number) => (
                  <Timeline.Item key={i} title={e.title}>
                    <Text size="xs" c="dimmed">{e.date || "дата не указана"}</Text>
                    {e.detail && <Text size="sm">{e.detail}</Text>}
                  </Timeline.Item>
                ))}
              </Timeline>
            ) : (
              <Text c="dimmed">Событий нет</Text>
            )}
          </Paper>
        </Tabs.Panel>

        <Tabs.Panel value="factors">
          <Paper withBorder radius="md" p="md">
            <SimpleGrid cols={{ base: 1, sm: 2 }}>
              {(p.factors || []).map((f: any, i: number) => (
                <Group key={i} justify="space-between" wrap="nowrap">
                  <Text size="sm">{f.factor}</Text>
                  <Badge color="indigo" variant="light">+{f.points}</Badge>
                </Group>
              ))}
            </SimpleGrid>
            {!p.factors?.length && <Text c="dimmed">Факторов нет</Text>}
          </Paper>
        </Tabs.Panel>

        <Tabs.Panel value="admin">
          <Paper withBorder radius="md" p="md">
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Материал</Table.Th>
                  <Table.Th>Дата</Table.Th>
                  <Table.Th>Квалификация</Table.Th>
                  <Table.Th>Решение</Table.Th>
                  <Table.Th>Мера</Table.Th>
                  {user?.can_export && <Table.Th>Акты</Table.Th>}
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {(p.admin_cases || []).map((c: any) => (
                  <Table.Tr key={c.id}>
                    <Table.Td>{c.material_no || "—"}</Table.Td>
                    <Table.Td>{c.case_date || "—"}</Table.Td>
                    <Table.Td>{c.qualification || "—"}</Table.Td>
                    <Table.Td>{c.decision || "—"}</Table.Td>
                    <Table.Td>{c.measure || "—"}</Table.Td>
                    {user?.can_export && (
                      <Table.Td>
                        <Menu>
                          <Menu.Target>
                            <Anchor size="sm">акт ▾</Anchor>
                          </Menu.Target>
                          <Menu.Dropdown>
                            <Menu.Item onClick={() => download("protest", c.id)}>Протест по материалу</Menu.Item>
                            <Menu.Item onClick={() => download("appeal", c.id)}>Апелляционное ходатайство</Menu.Item>
                          </Menu.Dropdown>
                        </Menu>
                      </Table.Td>
                    )}
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
            {!p.admin_cases?.length && <Text c="dimmed">Дел нет</Text>}
          </Paper>
        </Tabs.Panel>

        <Tabs.Panel value="preventive">
          <Paper withBorder radius="md" p="md">
            <Table striped>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Форма</Table.Th>
                  <Table.Th>Категория</Table.Th>
                  <Table.Th>Статус</Table.Th>
                  <Table.Th>Поставлен</Table.Th>
                  <Table.Th>Снят</Table.Th>
                  <Table.Th>Спец-предписание</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {(p.preventive_records || []).map((r: any) => (
                  <Table.Tr key={r.id}>
                    <Table.Td>{r.form || "—"}</Table.Td>
                    <Table.Td>{r.category || "—"}</Table.Td>
                    <Table.Td>{r.status || "—"}</Table.Td>
                    <Table.Td>{r.date_post || "—"}</Table.Td>
                    <Table.Td>{r.date_removed || "—"}</Table.Td>
                    <Table.Td>{r.has_special_req ? <Badge color="teal">да</Badge> : "—"}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
            {!p.preventive_records?.length && <Text c="dimmed">Записей нет</Text>}
          </Paper>
        </Tabs.Panel>

        <Tabs.Panel value="suspects">
          <Paper withBorder radius="md" p="md">
            <Table striped>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>ЕРДР</Table.Th>
                  <Table.Th>Год</Table.Th>
                  <Table.Th>Квалификация</Table.Th>
                  <Table.Th>Тяжесть</Table.Th>
                  <Table.Th>Регион</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {(p.suspects || []).map((s: any) => (
                  <Table.Tr key={s.id}>
                    <Table.Td>{s.erdr_no || "—"}</Table.Td>
                    <Table.Td>{s.erdr_year || "—"}</Table.Td>
                    <Table.Td>{s.qualification || "—"}</Table.Td>
                    <Table.Td>{s.gravity || "—"}</Table.Td>
                    <Table.Td>{s.region || "—"}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
            {!p.suspects?.length && <Text c="dimmed">Сведений нет</Text>}
          </Paper>
        </Tabs.Panel>

        <Tabs.Panel value="support">
          <Stack gap="md">
            {support?.gaps?.length ? (
              <Alert color="orange" variant="light" title="Разрывы реестров">
                <List size="sm">
                  {support.gaps.map((g, i) => <List.Item key={i}>{g}</List.Item>)}
                </List>
              </Alert>
            ) : null}
            <Paper withBorder radius="md" p="md">
              <Text fw={600} mb="sm">Коды МКБ-10</Text>
              {support?.icd_codes?.length ? (
                <Table striped>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Код</Table.Th>
                      <Table.Th>Диагноз</Table.Th>
                      <Table.Th>Источник</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {support.icd_codes.map((c) => (
                      <Table.Tr key={`${c.source}-${c.code}`}>
                        <Table.Td><Badge variant="light">{c.code}</Badge></Table.Td>
                        <Table.Td>{c.title_ru}</Table.Td>
                        <Table.Td>{c.source === "narco" ? "наркология" : c.source === "psych" ? "психиатрия" : c.source}</Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              ) : (
                <Text c="dimmed" size="sm">
                  Коды не привязаны. Администратор может импортировать из registry_crossmatch («Импорт МКБ из реестра»).
                </Text>
              )}
            </Paper>
            <Paper withBorder radius="md" p="md">
              <Group justify="space-between" mb="sm">
                <Text fw={600}>Меры государственной поддержки</Text>
                <Anchor component={Link} to="/legal" size="sm">Нормативная база →</Anchor>
              </Group>
              {support?.entitlements?.length ? (
                <Stack gap="sm">
                  {support.entitlements.map((e) => (
                    <Card key={e.id} withBorder padding="sm">
                      <Group justify="space-between" mb={4}>
                        <Badge variant="light">{e.category}</Badge>
                        <Anchor href={e.adilet_url} target="_blank" rel="noreferrer" size="xs">
                          {e.legal_article} <IconExternalLink size={10} />
                        </Anchor>
                      </Group>
                      <Text fw={600} size="sm">{e.title}</Text>
                      <Text size="xs" c="dimmed">{e.condition_text}</Text>
                    </Card>
                  ))}
                </Stack>
              ) : (
                <Text c="dimmed" size="sm">Нет связанных выплат — привяжите код МКБ или обновите справочник.</Text>
              )}
            </Paper>
            {support?.subordinate_acts?.length ? (
              <Paper withBorder radius="md" p="md">
                <Text fw={600} mb="sm">Подзаконные акты (adilet)</Text>
                <Stack gap={6}>
                  {support.subordinate_acts.map((a) => (
                    <Anchor key={a.adilet_url} href={a.adilet_url} target="_blank" rel="noreferrer" size="sm">
                      {a.title} <IconExternalLink size={12} />
                    </Anchor>
                  ))}
                </Stack>
              </Paper>
            ) : null}
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="measures">
          <Stack>
            {measures.length === 0 && (
              <Paper withBorder radius="md" p="md">
                <Text c="dimmed">Рекомендованных мер не выявлено.</Text>
              </Paper>
            )}
            {measures.map((m: any, i: number) => (
              <Card key={i} withBorder radius="md" padding="md">
                <Group justify="space-between" align="flex-start" wrap="nowrap">
                  <Group gap="sm" align="flex-start" wrap="nowrap">
                    <ThemeIcon variant="light" color={m.applicable ? "indigo" : "gray"}>
                      <IconShieldCheck size={18} />
                    </ThemeIcon>
                    <div>
                      <Group gap="xs">
                        <Text fw={600}>{m.title}</Text>
                        <Badge size="xs" color={m.applicable ? "teal" : "gray"} variant="light">
                          {m.applicable ? "рекомендуется" : "оснований нет"}
                        </Badge>
                      </Group>
                      <Text size="sm">{m.reason}</Text>
                      {Array.isArray(m.legal_basis) && (
                        <Text size="xs" c="dimmed" mt={4}>
                          Основание: {m.legal_basis.join("; ")}
                        </Text>
                      )}
                    </div>
                  </Group>
                  {user?.can_export && m.type && (
                    <Button size="xs" variant="light" onClick={() => download(m.type)} loading={busy === m.type}>
                      Сформировать
                    </Button>
                  )}
                </Group>
              </Card>
            ))}
          </Stack>
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
