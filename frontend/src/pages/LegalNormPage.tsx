import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Anchor, Badge, Card, Group, Stack, Text, Title } from "@mantine/core";
import { IconArrowLeft, IconExternalLink } from "@tabler/icons-react";
import api, { Norm } from "../api";
import { PageLoader } from "../components/LoadingSkeleton";
import ErrorState from "../components/ErrorState";

const STATUS_COLOR: Record<string, string> = {
  действует: "teal", "утратил силу": "red", "утратила силу": "red", изменена: "yellow",
};

export default function LegalNormPage() {
  const { id } = useParams();
  const [norm, setNorm] = useState<Norm | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<Norm>(`/legal/norms/${id}`)
      .then((r) => setNorm(r.data))
      .catch(() => setError("Норма не найдена"))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <PageLoader />;
  if (error || !norm) return <ErrorState message={error || "Не найдено"} />;

  return (
    <Stack>
      <Anchor component={Link} to="/legal" size="sm"><IconArrowLeft size={14} style={{ verticalAlign: "middle" }} /> К НПА</Anchor>
      <Card withBorder padding="lg">
        <Group gap="xs" mb="sm">
          <Badge variant="light">{norm.act}</Badge>
          {norm.article && <Badge color="indigo">{norm.article}</Badge>}
          {norm.point && <Badge>{`п.${norm.point}`}</Badge>}
          <Badge color={STATUS_COLOR[norm.status] || "gray"} variant="dot">{norm.status}</Badge>
        </Group>
        {norm.title && <Title order={3} mb="md">{norm.title}</Title>}
        <Group gap="md" mb="md">
          {norm.category && <Text size="sm" c="dimmed">Категория: {norm.category}</Text>}
          {norm.subject && <Text size="sm" c="dimmed">Субъект: {norm.subject}</Text>}
          {norm.measure && <Text size="sm" c="dimmed">Мера: {norm.measure}</Text>}
          {norm.edition_start && <Text size="sm" c="dimmed">Ред. с: {norm.edition_start}</Text>}
        </Group>
        <Text style={{ whiteSpace: "pre-wrap" }}>{norm.text_ru}</Text>
        {norm.source_url && (
          <Anchor href={norm.source_url} target="_blank" mt="md" size="sm">
            Источник на adilet <IconExternalLink size={12} />
          </Anchor>
        )}
      </Card>
    </Stack>
  );
}
