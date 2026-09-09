import { useState } from "react";
import {
  Paper, TextInput, PasswordInput, Button, Title, Text, Stack, Center, Image, Alert, Box,
} from "@mantine/core";
import { IconAlertCircle, IconLock } from "@tabler/icons-react";
import { useNavigate } from "react-router-dom";
import api from "../api";
import { useAuth } from "../auth";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [totp, setTotp] = useState("");
  const [need2fa, setNeed2fa] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await api.post("/auth/login", {
        username,
        password,
        totp_code: totp || undefined,
      });
      await login(data.access_token, data.refresh_token);
      if (data.requires_password_change) {
        navigate("/settings?change_password=1");
      } else {
        navigate("/");
      }
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Ошибка входа";
      if (detail.includes("2FA")) setNeed2fa(true);
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box
      style={{
        minHeight: "100vh",
        background: "linear-gradient(135deg, #0b1f4d 0%, #16357a 100%)",
      }}
    >
      <Center h="100vh">
        <Paper shadow="xl" radius="lg" p="xl" w={400}>
          <Stack align="center" gap="xs" mb="md">
            <Image src="/emblem.png" h={80} w={80} fit="contain" alt="Герб" />
            <Title order={3} ta="center">
              Профилактика 360
            </Title>
            <Text size="sm" c="dimmed" ta="center">
              Информационно-аналитическая система прокуратуры Алматинской области
            </Text>
          </Stack>

          <form onSubmit={submit}>
            <Stack>
              <TextInput
                label="Имя пользователя"
                placeholder="admin"
                value={username}
                onChange={(e) => setUsername(e.currentTarget.value)}
                required
                autoFocus
              />
              <PasswordInput
                label="Пароль"
                value={password}
                onChange={(e) => setPassword(e.currentTarget.value)}
                required
              />
              {need2fa && (
                <TextInput
                  label="Код 2FA"
                  placeholder="123456"
                  value={totp}
                  onChange={(e) => setTotp(e.currentTarget.value)}
                  leftSection={<IconLock size={16} />}
                />
              )}
              {error && (
                <Alert color="red" icon={<IconAlertCircle size={16} />} variant="light">
                  {error}
                </Alert>
              )}
              <Button type="submit" fullWidth loading={loading}>
                Войти
              </Button>
            </Stack>
          </form>
        </Paper>
      </Center>
    </Box>
  );
}
