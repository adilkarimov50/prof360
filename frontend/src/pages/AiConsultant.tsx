import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Title, Stack, Textarea, Button, Card, Text, Badge, Group, Paper, Alert, ScrollArea,
  Divider, Anchor, Chip, TypographyStylesProvider, Loader, ThemeIcon,
} from "@mantine/core";
import { IconRobot, IconAlertTriangle, IconSend, IconUser } from "@tabler/icons-react";
import Markdown from "react-markdown";
import api from "../api";

interface Source {
  norm_id: number;
  ref: string;
  status: string;
  edition: string | null;
  source_url: string | null;
}
interface Msg {
  q: string;
  answer: string;
  sources: Source[];
  warnings: string[];
  confidence: number;
  used_llm: boolean;
  streaming?: boolean;
}

const QUICK = [
  "Как реагировать на необоснованное прекращение дела по ст.73 КоАП?",
  "Какие акты прокурорского реагирования возможны по Приказу №32?",
  "Основания и срок для апелляционного ходатайства по адм. делу?",
  "Когда лицо подлежит постановке на профилактический учёт?",
];

export default function AiConsultant() {
  const [searchParams] = useSearchParams();
  const contextType = searchParams.get("context_type");
  const contextId = searchParams.get("context_id");
  const [question, setQuestion] = useState(searchParams.get("q") || "");
  const [history, setHistory] = useState<Msg[]>([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<any>(null);
  const viewport = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.get("/ai/status").then((r) => setStatus(r.data)).catch(() => {});
  }, []);

  const scrollDown = () =>
    setTimeout(() => viewport.current?.scrollTo({ top: 9e9, behavior: "smooth" }), 30);

  const patchLast = (patch: Partial<Msg>) =>
    setHistory((h) => {
      if (h.length === 0) return h;
      const copy = [...h];
      copy[copy.length - 1] = { ...copy[copy.length - 1], ...patch };
      return copy;
    });

  const ask = async (text: string) => {
    if (!text.trim() || loading) return;
    setLoading(true);
    setQuestion("");

    const priorTurns = history.flatMap((m) => [
      { role: "user", content: m.q },
      { role: "assistant", content: m.answer },
    ]);
    // Сообщение пользователя и «пустой» ответ появляются сразу (оптимистично).
    setHistory((h) => [
      ...h,
      { q: text, answer: "", sources: [], warnings: [], confidence: 0, used_llm: false, streaming: true },
    ]);
    scrollDown();

    try {
      const resp = await fetch("/api/ai/chat/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token") || ""}`,
        },
        body: JSON.stringify({
          question: text,
          history: priorTurns,
          context_type: contextType || undefined,
          context_id: contextId || undefined,
        }),
      });
      if (!resp.ok || !resp.body) throw new Error("stream failed");

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() ?? "";
        for (const part of parts) {
          const line = part.split("\n").find((l) => l.startsWith("data:"));
          if (!line) continue;
          const raw = line.slice(5).trim();
          if (!raw) continue;
          let evt: any;
          try {
            evt = JSON.parse(raw);
          } catch {
            continue;
          }
          if (evt.type === "delta") {
            patchLast({ answer: evt.answer });
            scrollDown();
          } else if (evt.type === "done") {
            patchLast({
              answer: evt.answer,
              sources: evt.sources,
              warnings: evt.warnings,
              confidence: evt.confidence,
              used_llm: evt.used_llm,
              streaming: false,
            });
            scrollDown();
          } else if (evt.type === "error") {
            patchLast({ answer: "Не удалось получить ответ. Повторите попытку.", streaming: false });
          }
        }
      }
      patchLast({ streaming: false });
    } catch {
      patchLast({
        answer: "Ошибка соединения с ИИ-консультантом. Повторите попытку.",
        streaming: false,
      });
    } finally {
      setLoading(false);
      scrollDown();
    }
  };

  return (
    <Stack h="calc(100vh - 92px)">
      <Group justify="space-between">
        <Title order={2}>ИИ-консультант</Title>
        {status && (
          <Group gap="xs">
            <Badge color={status.available ? "teal" : "gray"} variant="light">
              {status.provider} · {status.model}
            </Badge>
            <Badge color={status.available ? "teal" : "red"} variant="dot">
              {status.available ? "онлайн" : "RAG-фолбэк"}
            </Badge>
          </Group>
        )}
      </Group>

      <Alert color="indigo" variant="light" icon={<IconRobot size={18} />}>
        Консультант работает как прокурор-аналитик: объясняет простым юридическим языком,
        опирается только на нормы из базы (статья и пункт — из карточки нормы, без выдумок).
        Персональные данные обезличиваются перед отправкой во внешний ИИ.
      </Alert>

      <Paper withBorder radius="md" style={{ flex: 1, overflow: "hidden" }}>
        <ScrollArea h="100%" viewportRef={viewport} p="md">
          {history.length === 0 && (
            <Stack align="center" gap="sm" py="xl">
              <ThemeIcon size={56} radius="xl" variant="light" color="indigo">
                <IconRobot size={32} />
              </ThemeIcon>
              <Text c="dimmed" ta="center">
                Задайте вопрос по профилактике правонарушений, мерам реагирования или нормам права.
              </Text>
              <Group justify="center" gap="xs" maw={720}>
                {QUICK.map((qt) => (
                  <Chip key={qt} variant="outline" onClick={() => ask(qt)} checked={false}>
                    {qt}
                  </Chip>
                ))}
              </Group>
            </Stack>
          )}

          <Stack gap="lg">
            {history.map((m, i) => (
              <div key={i}>
                <Group gap="xs" mb={4} justify="flex-end">
                  <Card withBorder radius="md" bg="indigo.0" ml={40} py={8} px="md">
                    <Text size="sm">{m.q}</Text>
                  </Card>
                  <ThemeIcon variant="light" color="indigo" radius="xl">
                    <IconUser size={16} />
                  </ThemeIcon>
                </Group>

                <Group gap="xs" align="flex-start" wrap="nowrap">
                  <ThemeIcon variant="light" color="teal" radius="xl">
                    <IconRobot size={16} />
                  </ThemeIcon>
                  <Card withBorder radius="md" mr={40} style={{ flex: 1 }}>
                    {m.streaming && !m.answer ? (
                      <Group gap="xs">
                        <Loader type="dots" size="sm" />
                        <Text size="sm" c="dimmed">ИИ-консультант печатает…</Text>
                      </Group>
                    ) : (
                      <TypographyStylesProvider fz="sm">
                        <Markdown>{m.answer + (m.streaming ? " ▌" : "")}</Markdown>
                      </TypographyStylesProvider>
                    )}

                    {m.warnings?.map((w, j) => (
                      <Alert key={j} color="yellow" variant="light" mt="xs" py={6}
                        icon={<IconAlertTriangle size={14} />}>
                        <Text size="xs">{w}</Text>
                      </Alert>
                    ))}

                    {!m.streaming && m.sources?.length > 0 && (
                      <>
                        <Divider my="xs" label="Источники" labelPosition="left" />
                        <Group gap="xs">
                          {m.sources.map((s) => (
                            <Badge key={s.norm_id} variant="outline"
                              color={s.status === "действует" ? "teal" : "red"}>
                              {s.source_url ? (
                                <Anchor href={s.source_url} target="_blank" inherit>
                                  {s.ref}
                                </Anchor>
                              ) : (
                                s.ref
                              )}
                            </Badge>
                          ))}
                          {m.confidence > 0 && (
                            <Badge color="gray" variant="light">
                              уверенность {Math.round(m.confidence * 100)}%
                            </Badge>
                          )}
                        </Group>
                      </>
                    )}
                  </Card>
                </Group>
              </div>
            ))}
          </Stack>
        </ScrollArea>
      </Paper>

      <Group align="flex-end" gap="xs">
        <Textarea
          flex={1}
          autosize
          minRows={1}
          maxRows={5}
          placeholder="Введите вопрос…  (Enter — отправить, Shift+Enter — новая строка)"
          value={question}
          onChange={(e) => setQuestion(e.currentTarget.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              ask(question);
            }
          }}
        />
        <Button
          onClick={() => ask(question)}
          loading={loading}
          leftSection={<IconSend size={16} />}
          h={42}
        >
          Отправить
        </Button>
      </Group>
    </Stack>
  );
}
