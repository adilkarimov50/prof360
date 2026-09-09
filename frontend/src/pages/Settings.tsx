import { useState } from "react";
import { Alert, Button, Card, Group, Stack, Text, TextInput, Badge, PasswordInput } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "../auth";
import api, { ROLE_LABELS, saveTokens } from "../api";
import PageHeader from "../components/PageHeader";

export default function Settings() {
  const { user, refresh } = useAuth();
  const [searchParams] = useSearchParams();
  const forceChange = searchParams.get("change_password") === "1" || user?.must_change_password;
  const [totpSecret, setTotpSecret] = useState("");
  const [provisioningUri, setProvisioningUri] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const setup2fa = async () => {
    setLoading(true);
    try {
      const { data } = await api.post("/auth/2fa/setup");
      setTotpSecret(data.secret);
      setProvisioningUri(data.provisioning_uri);
      notifications.show({ color: "blue", title: "2FA", message: "Отсканируйте QR или введите секрет в приложение" });
    } catch {
      notifications.show({ color: "red", title: "Ошибка настройки 2FA", message: "Повторите попытку" });
    } finally {
      setLoading(false);
    }
  };

  const enable2fa = async () => {
    setLoading(true);
    try {
      await api.post("/auth/2fa/enable", { code });
      notifications.show({ color: "teal", title: "2FA включена", message: "Двухфакторная аутентификация активна" });
      setTotpSecret("");
      await refresh();
    } catch {
      notifications.show({ color: "red", title: "Неверный код подтверждения", message: "Проверьте код в приложении" });
    } finally {
      setLoading(false);
    }
  };

  const changePassword = async () => {
    if (newPassword !== confirmPassword) {
      notifications.show({ color: "red", title: "Пароли не совпадают", message: "Введите одинаковые значения" });
      return;
    }
    setLoading(true);
    try {
      const { data } = await api.post("/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      saveTokens(data.access_token, data.refresh_token);
      notifications.show({ color: "teal", title: "Пароль изменён", message: "Новый пароль сохранён" });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      await refresh();
    } catch {
      notifications.show({ color: "red", title: "Не удалось сменить пароль", message: "Проверьте текущий пароль" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Stack>
      <PageHeader title="Настройки профиля" />
      {forceChange && (
        <Alert color="orange" title="Требуется смена пароля">
          Для безопасности смените пароль по умолчанию перед продолжением работы.
        </Alert>
      )}
      <Card withBorder padding="lg">
        <Stack gap="sm">
          <Text fw={600}>{user?.full_name}</Text>
          <Text size="sm" c="dimmed">Логин: {user?.username}</Text>
          <Text size="sm" c="dimmed">Роль: {ROLE_LABELS[user?.role || ""] || user?.role}</Text>
          {user?.district && <Text size="sm" c="dimmed">Район: {user.district}</Text>}
          <Group gap="xs">
            {user?.can_export && <Badge color="teal">Экспорт</Badge>}
            {user?.can_access_minors && <Badge color="blue">Доступ к несовершеннолетним</Badge>}
            <Badge color={user?.totp_enabled ? "teal" : "gray"}>
              2FA: {user?.totp_enabled ? "включена" : "выключена"}
            </Badge>
          </Group>
        </Stack>
      </Card>

      <Card withBorder padding="lg">
        <Text fw={600} mb="md">Смена пароля</Text>
        <Stack gap="sm">
          <PasswordInput label="Текущий пароль" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} />
          <PasswordInput label="Новый пароль" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
          <PasswordInput label="Подтверждение" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
          <Button onClick={changePassword} loading={loading}>Сменить пароль</Button>
        </Stack>
      </Card>

      {!user?.totp_enabled && (
        <Card withBorder padding="lg">
          <Text fw={600} mb="md">Двухфакторная аутентификация</Text>
          {!totpSecret ? (
            <Button onClick={setup2fa} loading={loading}>Настроить 2FA</Button>
          ) : (
            <Stack gap="sm">
              <Alert color="blue" title="Секрет TOTP">
                <Text ff="monospace" size="sm">{totpSecret}</Text>
                {provisioningUri && (
                  <Text size="xs" c="dimmed" mt="xs" style={{ wordBreak: "break-all" }}>{provisioningUri}</Text>
                )}
              </Alert>
              <TextInput label="Код из приложения" value={code} onChange={(e) => setCode(e.target.value)} />
              <Button onClick={enable2fa} loading={loading}>Подтвердить и включить</Button>
            </Stack>
          )}
        </Card>
      )}
    </Stack>
  );
}
