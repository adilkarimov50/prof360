import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Anchor, Badge, Button, Group, Paper, ScrollArea, Stack, Text, TextInput, Title,
} from "@mantine/core";
import { IconArrowLeft, IconDownload, IconExternalLink, IconSearch } from "@tabler/icons-react";
import api from "../api";
import { PageLoader } from "../components/LoadingSkeleton";
import ErrorState from "../components/ErrorState";

interface DocText {
  doc_id: string;
  title: string;
  number: string | null;
  act_type: string;
  adilet_url: string;
  text: string;
}

export default function LegalDocumentReader() {
  const { docId } = useParams();
  const [doc, setDoc] = useState<DocText | null>(null);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    if (!docId) return;
    setLoading(true);
    api.get<DocText>(`/legal/documents/${docId}/text`)
      .then((r) => setDoc(r.data))
      .catch(() => setError("Не удалось загрузить текст документа"))
      .finally(() => setLoading(false));
  }, [docId]);

  const highlighted = useMemo(() => {
    if (!doc?.text) return "";
    if (!q.trim()) return doc.text;
    const re = new RegExp(q.trim().replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
    return doc.text.replace(re, (m) => `⟦${m}⟧`);
  }, [doc, q]);

  const download = async (kind: "docx" | "txt") => {
    if (!docId) return;
    setBusy(kind);
    try {
      const url = kind === "docx"
        ? `/legal/documents/${docId}/download`
        : `/legal/documents/${docId}/download.txt`;
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

  if (loading) return <PageLoader />;
  if (error || !doc) return <ErrorState message={error || "Документ не найден"} />;

  return (
    <Stack h="calc(100vh - 120px)">
      <Group justify="space-between" wrap="wrap">
        <Anchor component={Link} to="/legal" size="sm">
          <IconArrowLeft size={14} style={{ verticalAlign: "middle" }} /> К нормативной базе
        </Anchor>
        <Group>
          <Button
            variant="light"
            leftSection={<IconDownload size={16} />}
            loading={busy === "docx"}
            onClick={() => download("docx")}
          >
            Скачать DOCX
          </Button>
          <Button
            variant="default"
            leftSection={<IconDownload size={16} />}
            loading={busy === "txt"}
            onClick={() => download("txt")}
          >
            Скачать TXT
          </Button>
          <Button component="a" href={doc.adilet_url} target="_blank" rel="noreferrer" variant="subtle">
            adilet <IconExternalLink size={14} />
          </Button>
        </Group>
      </Group>

      <Paper withBorder p="md">
        <Group gap="xs" mb="xs">
          <Badge>{doc.act_type}</Badge>
          {doc.number && <Badge variant="light">№{doc.number}</Badge>}
        </Group>
        <Title order={3}>{doc.title}</Title>
        <TextInput
          mt="md"
          placeholder="Поиск по тексту документа…"
          leftSection={<IconSearch size={16} />}
          value={q}
          onChange={(e) => setQ(e.currentTarget.value)}
        />
      </Paper>

      <Paper withBorder p="md" style={{ flex: 1, minHeight: 0 }}>
        <ScrollArea h="100%" type="auto">
          <Text component="pre" style={{ whiteSpace: "pre-wrap", fontFamily: "inherit", fontSize: 14, lineHeight: 1.55 }}>
            {highlighted.split("⟦").map((chunk, i) => {
              if (i === 0) return chunk;
              const end = chunk.indexOf("⟧");
              if (end === -1) return chunk;
              const hit = chunk.slice(0, end);
              const rest = chunk.slice(end + 1);
              return (
                <span key={i}>
                  <mark>{hit}</mark>
                  {rest}
                </span>
              );
            })}
          </Text>
        </ScrollArea>
      </Paper>
    </Stack>
  );
}
