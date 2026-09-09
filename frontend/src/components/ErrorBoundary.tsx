import { Component, ReactNode } from "react";
import { Alert, Button, Center, Stack } from "@mantine/core";

interface Props { children: ReactNode }
interface State { hasError: boolean }

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <Center h="100vh">
          <Stack align="center">
            <Alert color="red" title="Критическая ошибка интерфейса" maw={480}>
              Перезагрузите страницу. Если ошибка повторяется — обратитесь к администратору.
            </Alert>
            <Button onClick={() => window.location.reload()}>Перезагрузить</Button>
          </Stack>
        </Center>
      );
    }
    return this.props.children;
  }
}
