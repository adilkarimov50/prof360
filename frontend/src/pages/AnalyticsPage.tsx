import { useEffect, useState } from "react";
import { Anchor, Badge, Card, Stack, Table, Tabs, Text } from "@mantine/core";
import { Link } from "react-router-dom";
import api, { RISK_COLORS } from "../api";
import PageHeader from "../components/PageHeader";
import { PageLoader } from "../components/LoadingSkeleton";
import ErrorState from "../components/ErrorState";
import EmptyState from "../components/EmptyState";

import type { AnalyticsArticle, AnalyticsEscalation, AnalyticsRepeat } from "../types/api";

export default function AnalyticsPage() {
  const [repeat, setRepeat] = useState<AnalyticsRepeat[]>([]);
  const [escalation, setEscalation] = useState<AnalyticsEscalation[]>([]);
  const [articles, setArticles] = useState<AnalyticsArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api.get("/analytics/repeat-offenders"),
      api.get("/analytics/escalation"),
      api.get("/analytics/articles"),
    ])
      .then(([r, e, a]) => {
        setRepeat(r.data);
        setEscalation(e.data);
        setArticles(a.data);
      })
      .catch(() => setError("Ошибка загрузки аналитики"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <PageLoader />;
  if (error) return <ErrorState message={error} />;

  return (
    <Stack>
      <PageHeader title="Аналитика" subtitle="Повторность, эскалация, топ статей КоАП" />
      <Tabs defaultValue="repeat">
        <Tabs.List mb="md">
          <Tabs.Tab value="repeat">Повторные нарушители ({repeat.length})</Tabs.Tab>
          <Tabs.Tab value="escalation">Эскалация учёт → ЕРДР ({escalation.length})</Tabs.Tab>
          <Tabs.Tab value="articles">Топ статей ({articles.length})</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="repeat">
          <Card withBorder padding="md">
            {repeat.length === 0 ? <EmptyState /> : (
              <Table striped highlightOnHover>
                <Table.Thead><Table.Tr><Table.Th>ФИО</Table.Th><Table.Th>Район</Table.Th><Table.Th>Дел</Table.Th><Table.Th>На учёте</Table.Th><Table.Th>Риск</Table.Th></Table.Tr></Table.Thead>
                <Table.Tbody>
                  {repeat.map((r) => (
                    <Table.Tr key={r.person_id}>
                      <Table.Td><Anchor component={Link} to={`/persons/${r.person_id}`}>{r.fio}</Anchor></Table.Td>
                      <Table.Td>{r.district || "—"}</Table.Td>
                      <Table.Td>{r.cases}</Table.Td>
                      <Table.Td>{r.on_register ? "да" : "нет"}</Table.Td>
                      <Table.Td><Badge color={RISK_COLORS[r.risk_level] || "gray"}>{r.risk_level}</Badge></Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )}
          </Card>
        </Tabs.Panel>
        <Tabs.Panel value="escalation">
          <Card withBorder padding="md">
            {escalation.length === 0 ? <EmptyState message="Эскалаций не выявлено" /> : (
              <Table striped highlightOnHover>
                <Table.Thead><Table.Tr><Table.Th>ФИО</Table.Th><Table.Th>Район</Table.Th><Table.Th>Учёт с</Table.Th><Table.Th>ЕРДР</Table.Th><Table.Th>Квалификация</Table.Th></Table.Tr></Table.Thead>
                <Table.Tbody>
                  {escalation.map((r, i) => (
                    <Table.Tr key={i}>
                      <Table.Td><Anchor component={Link} to={`/persons/${r.person_id}`}>{r.fio}</Anchor></Table.Td>
                      <Table.Td>{r.district || "—"}</Table.Td>
                      <Table.Td>{r.date_post || "—"}</Table.Td>
                      <Table.Td>{r.erdr_no || "—"}</Table.Td>
                      <Table.Td>{r.qualification || "—"}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )}
          </Card>
        </Tabs.Panel>
        <Tabs.Panel value="articles">
          <Card withBorder padding="md">
            <Table striped>
              <Table.Thead><Table.Tr><Table.Th>Статья</Table.Th><Table.Th>Количество дел</Table.Th></Table.Tr></Table.Thead>
              <Table.Tbody>
                {articles.map((a) => (
                  <Table.Tr key={a.article}><Table.Td>{a.article}</Table.Td><Table.Td>{a.count}</Table.Td></Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Card>
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
