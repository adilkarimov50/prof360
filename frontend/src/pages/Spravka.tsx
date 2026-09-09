import { useState } from "react";
import {
  Title, Stack, Card, Text, Group, Button, TextInput, SimpleGrid, ThemeIcon, Badge, Alert,
} from "@mantine/core";
import {
  IconFileText, IconBuildingCommunity, IconShieldCheck, IconReportAnalytics,
  IconAlertTriangle, IconTable, IconDownload, IconHeart, IconScaleOutline,
} from "@tabler/icons-react";
import { notifications } from "@mantine/notifications";
import api from "../api";
import { useAuth } from "../auth";

interface ReportDef {
  kind: string;
  title: string;
  desc: string;
  icon: any;
  color: string;
  format: "docx" | "xlsx";
}

const REPORTS: ReportDef[] = [
  {
    kind: "spravka_complex",
    title: "Комплексная справка (общая)",
    desc: "Сводная аналитическая справка по району: полиция + МИО, риск, реагирование.",
    icon: IconReportAnalytics,
    color: "indigo",
    format: "docx",
  },
  {
    kind: "spravka_police",
    title: "Справка по нарушениям полиции",
    desc: "Нарушения по линии ОВД: административная практика, профучёт, эскалация.",
    icon: IconShieldCheck,
    color: "blue",
    format: "docx",
  },
  {
    kind: "spravka_mio",
    title: "Справка по действиям МИО",
    desc: "Зона ответственности местных исполнительных органов: социальная профилактика.",
    icon: IconBuildingCommunity,
    color: "teal",
    format: "docx",
  },
  {
    kind: "spravka_health",
    title: "Справка по линии здравоохранения (ДСБ)",
    desc: "УБДБ, алкогольная преступность, исполнение поручений МВК Денсаулық сақтау басқармасы.",
    icon: IconHeart,
    color: "pink",
    format: "docx",
  },
  {
    kind: "adm_blocks",
    title: "Адм. практика: личность / дороги",
    desc: "Раздельный анализ ст. 73, 434, 440 КоАП и дорожной безопасности с рекомендациями по Приказу № 32.",
    icon: IconScaleOutline,
    color: "red",
    format: "docx",
  },
  {
    kind: "admin_violations",
    title: "Реестр нарушений адм. производства",
    desc: "Дела-кандидаты на проверку законности административного производства (XLSX).",
    icon: IconTable,
    color: "orange",
    format: "xlsx",
  },
  {
    kind: "district",
    title: "Справка по району",
    desc: "Краткая справка по показателям района.",
    icon: IconFileText,
    color: "grape",
    format: "docx",
  },
  {
    kind: "escalation",
    title: "Эскалация на профучёте (XLSX)",
    desc: "Лица, ставшие подозреваемыми в период нахождения на профилактическом учёте.",
    icon: IconAlertTriangle,
    color: "red",
    format: "xlsx",
  },
];

export default function Spravka() {
  const { user } = useAuth();
  const [district, setDistrict] = useState("");
  const [period, setPeriod] = useState("");
  const [busy, setBusy] = useState("");

  const generate = async (def: ReportDef) => {
    setBusy(def.kind);
    try {
      const payload: any = { kind: def.kind, format: def.format };
      if (district) payload.district = district;
      if (period) payload.period = period;
      const resp = await api.post("/reports/generate", payload, { responseType: "blob" });
      const cd = resp.headers["content-disposition"] || "";
      const m = /filename="?([^"]+)"?/.exec(cd);
      const fname = m ? m[1] : `${def.kind}.${def.format}`;
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = fname;
      a.click();
      URL.revokeObjectURL(url);
      notifications.show({ color: "teal", title: "Готово", message: fname });
    } catch (e: any) {
      notifications.show({
        color: "red",
        title: "Ошибка генерации",
        message: e?.response?.status === 403 ? "Недостаточно прав (экспорт)" : "Не удалось сформировать документ",
      });
    } finally {
      setBusy("");
    }
  };

  return (
    <Stack>
      <Title order={2}>Справки и акты реагирования</Title>

      {!user?.can_export && (
        <Alert color="yellow" variant="light" icon={<IconAlertTriangle size={16} />}>
          У вашей роли нет права экспорта документов. Обратитесь к администратору.
        </Alert>
      )}

      <Card withBorder radius="md" padding="md">
        <Group>
          <TextInput
            label="Район (опц.)"
            placeholder={user?.district || "вся область"}
            value={district}
            onChange={(e) => setDistrict(e.currentTarget.value)}
            disabled={!!user?.district}
            w={260}
          />
          <TextInput
            label="Период (опц.)"
            placeholder="напр. 2026"
            value={period}
            onChange={(e) => setPeriod(e.currentTarget.value)}
            w={180}
          />
        </Group>
        {user?.district && (
          <Text size="xs" c="dimmed" mt={6}>
            Охват ограничен вашим районом ({user.district}) согласно ABAC.
          </Text>
        )}
      </Card>

      <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
        {REPORTS.map((r) => {
          const Icon = r.icon;
          return (
            <Card key={r.kind} withBorder radius="md" padding="lg">
              <Group justify="space-between" mb="sm">
                <ThemeIcon size={44} radius="md" variant="light" color={r.color}>
                  <Icon size={24} />
                </ThemeIcon>
                <Badge variant="light" color="gray">{r.format.toUpperCase()}</Badge>
              </Group>
              <Text fw={600}>{r.title}</Text>
              <Text size="sm" c="dimmed" mb="md" mih={56}>
                {r.desc}
              </Text>
              <Button
                fullWidth
                variant="light"
                color={r.color}
                leftSection={<IconDownload size={16} />}
                loading={busy === r.kind}
                disabled={!user?.can_export}
                onClick={() => generate(r)}
              >
                Сформировать
              </Button>
            </Card>
          );
        })}
      </SimpleGrid>

      <Alert color="indigo" variant="light" icon={<IconReportAnalytics size={18} />}>
        Тексты справок структурируются ИИ (в стиле эталонной справки) с обязательной правовой
        привязкой; персональные данные обезличиваются. Документы помечаются водяным знаком и
        фиксируются в журнале аудита (DLP).
      </Alert>
    </Stack>
  );
}
