import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Stack, Group, TextInput, Button, Card, Text, Badge, Loader, Center,
  Paper, SimpleGrid, Anchor, Modal, ScrollArea, Table, Tabs, Accordion,
} from "@mantine/core";
import { IconSearch, IconScale, IconExternalLink, IconHeartHandshake, IconStethoscope, IconShieldCheck, IconBook, IconDownload } from "@tabler/icons-react";
import api, { Norm } from "../api";
import PageHeader from "../components/PageHeader";
import type { EntitlementItem, IcdCodeItem, LegalTopicBundle } from "../types/api";

interface Act {
  id: number;
  title: string;
  type: string;
  number: string | null;
  norms_count: number;
  source_url: string | null;
  doc_id?: string | null;
}

interface LegalDocumentRow {
  doc_id: string;
  title: string;
  number: string | null;
  act_type: string;
  cached: boolean;
  norms_count: number;
  docx_bytes: number | null;
}

function DocActions({ docId }: { docId: string }) {
  const [busy, setBusy] = useState("");
  const download = async (kind: "docx" | "txt") => {
    setBusy(kind);
    try {
      const url = kind === "docx" ? `/legal/documents/${docId}/download` : `/legal/documents/${docId}/download.txt`;
      const resp = await api.get(url, { responseType: "blob" });
      const cd = resp.headers["content-disposition"] || "";
      const m = /filename="?([^"]+)"?/.exec(cd);
      const fname = m?.[1] || `${docId}.${kind === "docx" ? "docx" : "txt"}`;
      const blobUrl = URL.createObjectURL(resp.data);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = fname;
      a.click();
      URL.revokeObjectURL(blobUrl);
    } finally {
      setBusy("");
    }
  };
  return (
    <Group gap={6}>
      <Button component={Link} to={`/legal/documents/${docId}`} size="xs" variant="light">Читать</Button>
      <Button size="xs" variant="default" loading={busy === "docx"} onClick={() => download("docx")} leftSection={<IconDownload size={12} />}>DOCX</Button>
      <Button size="xs" variant="subtle" loading={busy === "txt"} onClick={() => download("txt")}>TXT</Button>
    </Group>
  );
}

const STATUS_COLOR: Record<string, string> = {
  действует: "teal", "утратил силу": "red", "утратила силу": "red", изменена: "yellow",
};

const CATEGORY_COLOR: Record<string, string> = {
  "социальные выплаты": "blue",
  пособия: "green",
  пенсии: "grape",
  "медицинская помощь": "teal",
  профилактика: "orange",
  образование: "indigo",
};

export default function Legal() {
  const [tab, setTab] = useState<string | null>("library");
  const [acts, setActs] = useState<Act[]>([]);
  const [documents, setDocuments] = useState<LegalDocumentRow[]>([]);
  const [docQ, setDocQ] = useState("");
  const [topics, setTopics] = useState<Record<string, LegalTopicBundle>>({});
  const [entitlements, setEntitlements] = useState<EntitlementItem[]>([]);
  const [icdCodes, setIcdCodes] = useState<IcdCodeItem[]>([]);
  const [q, setQ] = useState("");
  const [icdQ, setIcdQ] = useState("");
  const [entQ, setEntQ] = useState("");
  const [results, setResults] = useState<Norm[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [actModal, setActModal] = useState<Act | null>(null);
  const [actNorms, setActNorms] = useState<Norm[]>([]);
  const [actLoading, setActLoading] = useState(false);
  const [bootLoading, setBootLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<Act[]>("/legal/acts"),
      api.get<Record<string, LegalTopicBundle>>("/legal/topics"),
      api.get<EntitlementItem[]>("/legal/entitlements"),
      api.get<IcdCodeItem[]>("/legal/icd-codes"),
      api.get<LegalDocumentRow[]>("/legal/documents"),
    ])
      .then(([a, t, e, icd, docs]) => {
        setActs(a.data);
        setTopics(t.data);
        setEntitlements(e.data);
        setIcdCodes(icd.data);
        setDocuments(docs.data);
      })
      .finally(() => setBootLoading(false));
  }, []);

  const entCategories = useMemo(
    () => [...new Set(entitlements.map((e) => e.category))].sort(),
    [entitlements],
  );

  const filteredEntitlements = useMemo(() => {
    if (!entQ.trim()) return entitlements;
    const s = entQ.toLowerCase();
    return entitlements.filter(
      (e) =>
        e.title.toLowerCase().includes(s)
        || e.beneficiary.toLowerCase().includes(s)
        || e.condition_text.toLowerCase().includes(s),
    );
  }, [entitlements, entQ]);

  const filteredDocs = useMemo(() => {
    if (!docQ.trim()) return documents;
    const s = docQ.toLowerCase();
    return documents.filter(
      (d) => d.title.toLowerCase().includes(s) || (d.number || "").toLowerCase().includes(s) || d.act_type.includes(s),
    );
  }, [documents, docQ]);

  const filteredIcd = useMemo(() => {
    if (!icdQ.trim()) return icdCodes;
    const s = icdQ.toLowerCase();
    return icdCodes.filter(
      (c) => c.code.toLowerCase().includes(s) || c.title_ru.toLowerCase().includes(s),
    );
  }, [icdCodes, icdQ]);

  const search = async () => {
    if (q.trim().length < 2) return;
    setLoading(true);
    setSearched(true);
    setTab("acts");
    try {
      const { data } = await api.get<Norm[]>("/legal/search", { params: { q } });
      setResults(data);
    } finally {
      setLoading(false);
    }
  };

  const openAct = async (act: Act) => {
    setActModal(act);
    setActLoading(true);
    try {
      const { data } = await api.get<Norm[]>(`/legal/acts/${act.id}/norms`);
      setActNorms(data);
    } finally {
      setActLoading(false);
    }
  };

  if (bootLoading) return <Center h="60vh"><Loader /></Center>;

  return (
    <Stack>
      <PageHeader
        title="Нормативно-правовая база"
        subtitle="Полные тексты с adilet.zan.kz — читать в системе или скачать DOCX/TXT"
      />

      <Paper withBorder radius="md" p="md">
        <Group>
          <TextInput
            flex={1}
            placeholder="Семантический поиск по нормам (статья, выплата, профилактика…)"
            leftSection={<IconSearch size={16} />}
            value={q}
            onChange={(e) => setQ(e.currentTarget.value)}
            onKeyDown={(e) => e.key === "Enter" && search()}
          />
          <Button onClick={search} loading={loading}>Найти</Button>
        </Group>
      </Paper>

      <Tabs value={tab} onChange={setTab}>
        <Tabs.List>
          <Tabs.Tab value="library" leftSection={<IconBook size={16} />}>Библиотека ({documents.length})</Tabs.Tab>
          <Tabs.Tab value="acts" leftSection={<IconScale size={16} />}>НПА в системе</Tabs.Tab>
          <Tabs.Tab value="prevention" leftSection={<IconShieldCheck size={16} />}>Профилактика</Tabs.Tab>
          <Tabs.Tab value="subordinate" leftSection={<IconShieldCheck size={16} />}>Приказы МВД/МЗ</Tabs.Tab>
          <Tabs.Tab value="benefits" leftSection={<IconHeartHandshake size={16} />}>Выплаты и пособия</Tabs.Tab>
          <Tabs.Tab value="icd" leftSection={<IconStethoscope size={16} />}>Коды МКБ-10</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="library" pt="md">
          <Text size="sm" c="dimmed" mb="md">
            Все кодексы, законы и приказы из реестра. При первом открытии документ подгружается с adilet автоматически.
          </Text>
          <TextInput
            mb="md"
            placeholder="Поиск по названию или номеру…"
            leftSection={<IconSearch size={16} />}
            value={docQ}
            onChange={(e) => setDocQ(e.currentTarget.value)}
          />
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Документ</Table.Th>
                <Table.Th>Тип</Table.Th>
                <Table.Th>Кэш</Table.Th>
                <Table.Th>Норм в БД</Table.Th>
                <Table.Th>Действия</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {filteredDocs.map((d) => (
                <Table.Tr key={d.doc_id}>
                  <Table.Td>
                    <Text fw={600} size="sm" lineClamp={2}>{d.title}</Text>
                    {d.number && <Text size="xs" c="dimmed">№{d.number}</Text>}
                  </Table.Td>
                  <Table.Td>{d.act_type}</Table.Td>
                  <Table.Td>
                    <Badge color={d.cached ? "teal" : "gray"} variant="light">
                      {d.cached ? "скачан" : "по запросу"}
                    </Badge>
                  </Table.Td>
                  <Table.Td>{d.norms_count || "—"}</Table.Td>
                  <Table.Td><DocActions docId={d.doc_id} /></Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Tabs.Panel>

        <Tabs.Panel value="acts" pt="md">
          {searched && (
            <Paper withBorder radius="md" p="md" mb="md">
              <Text fw={600} mb="sm">Результаты поиска {loading ? "" : `(${results.length})`}</Text>
              {loading ? <Center h={120}><Loader /></Center> : (
                <Stack gap="sm">
                  {results.map((n) => (
                    <Card key={n.id} withBorder radius="md" padding="sm" component={Link} to={`/legal/norms/${n.id}`} style={{ textDecoration: "none", color: "inherit" }}>
                      <Group gap="xs" mb={4}>
                        <Badge variant="light">{n.act}</Badge>
                        {n.article && <Badge color="indigo">{n.article}</Badge>}
                        <Badge color={STATUS_COLOR[n.status] || "gray"} variant="dot">{n.status}</Badge>
                      </Group>
                      {n.title && <Text fw={500}>{n.title}</Text>}
                      {n.text_ru && <Text size="sm" c="dimmed" lineClamp={3}>{n.text_ru}</Text>}
                    </Card>
                  ))}
                </Stack>
              )}
            </Paper>
          )}
          <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
            {acts.map((a) => (
              <Card key={a.id} withBorder radius="md" padding="md" style={{ cursor: "pointer" }} onClick={() => openAct(a)}>
                <Group justify="space-between" wrap="nowrap">
                  <Group gap="sm" wrap="nowrap">
                    <IconScale size={22} color="#4263eb" />
                    <div>
                      <Text fw={600} size="sm" lineClamp={2}>{a.title}</Text>
                      <Text size="xs" c="dimmed">{a.type}{a.number ? ` · №${a.number}` : ""}</Text>
                    </div>
                  </Group>
                  <Badge variant="light" color="indigo">{a.norms_count}</Badge>
                </Group>
              </Card>
            ))}
          </SimpleGrid>
        </Tabs.Panel>

        <Tabs.Panel value="prevention" pt="md">
          <Text size="sm" c="dimmed" mb="md">
            Подборка ключевых актов с ссылками на полные тексты в ИПС «Әділет». Администратор может загрузить полные статьи через «Загрузить кодексы с adilet» в разделе Администрирование.
          </Text>
          <Accordion variant="separated">
            {Object.entries(topics).map(([key, bundle]) => (
              <Accordion.Item key={key} value={key}>
                <Accordion.Control>{bundle.title}</Accordion.Control>
                <Accordion.Panel>
                  <Stack gap="md">
                    {bundle.acts.map((act) => (
                      <Card key={act.doc_id} withBorder padding="md">
                        <Group justify="space-between" align="flex-start">
                          <div>
                            <Text fw={600}>{act.title}</Text>
                            <Text size="sm" c="dimmed">№{act.number}</Text>
                            {act.note && <Text size="sm" mt="xs">{act.note}</Text>}
                            <Group gap={6} mt="sm">
                              {act.key_articles.map((art) => (
                                <Badge key={art} variant="light" color="indigo">{art}</Badge>
                              ))}
                            </Group>
                          </div>
                          <Group gap="xs">
                            <DocActions docId={act.doc_id} />
                            <Anchor href={act.adilet_url} target="_blank" rel="noreferrer" size="sm">
                              adilet <IconExternalLink size={12} />
                            </Anchor>
                          </Group>
                        </Group>
                      </Card>
                    ))}
                  </Stack>
                </Accordion.Panel>
              </Accordion.Item>
            ))}
          </Accordion>
        </Tabs.Panel>

        <Tabs.Panel value="subordinate" pt="md">
          {topics.subordinate && (
            <Stack gap="md">
              <Text size="sm" c="dimmed">{topics.subordinate.title}</Text>
              {topics.subordinate.acts.map((act) => (
                <Card key={act.doc_id} withBorder padding="md">
                  <Group justify="space-between" align="flex-start">
                    <div>
                      <Text fw={600}>{act.title}</Text>
                      <Text size="sm" c="dimmed">№{act.number}</Text>
                      {act.note && <Text size="sm" mt="xs">{act.note}</Text>}
                    </div>
                    <Group gap="xs">
                      <DocActions docId={act.doc_id} />
                      <Anchor href={act.adilet_url} target="_blank" rel="noreferrer" size="sm">
                        adilet <IconExternalLink size={12} />
                      </Anchor>
                    </Group>
                  </Group>
                </Card>
              ))}
            </Stack>
          )}
        </Tabs.Panel>

        <Tabs.Panel value="benefits" pt="md">
          <TextInput
            mb="md"
            placeholder="Поиск по названию, категории получателей, условиям…"
            leftSection={<IconSearch size={16} />}
            value={entQ}
            onChange={(e) => setEntQ(e.currentTarget.value)}
          />
          {entCategories.map((cat) => {
            const items = filteredEntitlements.filter((e) => e.category === cat);
            if (!items.length) return null;
            return (
              <Stack key={cat} mb="lg">
                <Text fw={600}>{cat}</Text>
                <SimpleGrid cols={{ base: 1, md: 2 }}>
                  {items.map((e) => (
                    <Card key={e.id} withBorder padding="md">
                      <Group justify="space-between" mb="xs">
                        <Badge color={CATEGORY_COLOR[e.category] || "gray"}>{e.category}</Badge>
                        <Anchor href={e.adilet_url} target="_blank" rel="noreferrer" size="xs">
                          {e.legal_article} <IconExternalLink size={10} />
                        </Anchor>
                      </Group>
                      <Text fw={600} mb={4}>{e.title}</Text>
                      <Text size="sm" c="dimmed" mb="xs">Кому: {e.beneficiary}</Text>
                      <Text size="sm" mb="xs">{e.condition_text}</Text>
                      {e.amount_note && <Text size="sm" c="dimmed">Размер: {e.amount_note}</Text>}
                      <Text size="xs" c="dimmed" mt="xs">Исполнитель: {e.administering_body}</Text>
                      {e.prevention_relevance && (
                        <Text size="xs" mt="sm" c="orange">{e.prevention_relevance}</Text>
                      )}
                    </Card>
                  ))}
                </SimpleGrid>
              </Stack>
            );
          })}
        </Tabs.Panel>

        <Tabs.Panel value="icd" pt="md">
          <Text size="sm" c="dimmed" mb="md">
            Коды МКБ-10, релевантные профилактике (алкоголь, наркотики, психические расстройства, социальные факторы). Для каждого кода — связанные меры государственной поддержки.
          </Text>
          <TextInput
            mb="md"
            placeholder="Поиск по коду или названию (F10, алкоголь, безработица…)"
            leftSection={<IconSearch size={16} />}
            value={icdQ}
            onChange={(e) => setIcdQ(e.currentTarget.value)}
          />
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Код</Table.Th>
                <Table.Th>Название</Table.Th>
                <Table.Th>Глава</Table.Th>
                <Table.Th>Для профилактики</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {filteredIcd.map((c) => (
                <Table.Tr key={c.code}>
                  <Table.Td><Badge variant="light">{c.code}</Badge></Table.Td>
                  <Table.Td>{c.title_ru}</Table.Td>
                  <Table.Td>{c.chapter || "—"}</Table.Td>
                  <Table.Td><Text size="sm" lineClamp={2}>{c.prevention_note || "—"}</Text></Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Tabs.Panel>
      </Tabs>

      <Modal opened={!!actModal} onClose={() => setActModal(null)} title={actModal?.title} size="xl">
        {actLoading ? <Center h={200}><Loader /></Center> : (
          <ScrollArea h={400}>
            <Table striped highlightOnHover>
              <Table.Thead><Table.Tr><Table.Th>Статья</Table.Th><Table.Th>Название</Table.Th><Table.Th>Статус</Table.Th></Table.Tr></Table.Thead>
              <Table.Tbody>
                {actNorms.map((n) => (
                  <Table.Tr key={n.id}>
                    <Table.Td><Anchor component={Link} to={`/legal/norms/${n.id}`}>{n.article}{n.point ? ` п.${n.point}` : ""}</Anchor></Table.Td>
                    <Table.Td>{n.title || "—"}</Table.Td>
                    <Table.Td><Badge size="sm" color={STATUS_COLOR[n.status] || "gray"}>{n.status}</Badge></Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea>
        )}
        <Group mt="md">
          {actModal?.doc_id && <DocActions docId={actModal.doc_id} />}
          {actModal?.source_url && (
            <Anchor href={actModal.source_url} target="_blank" size="sm">adilet <IconExternalLink size={12} /></Anchor>
          )}
        </Group>
      </Modal>
    </Stack>
  );
}
