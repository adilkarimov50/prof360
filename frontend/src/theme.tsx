import { createContext, useContext, useEffect, useState, ReactNode } from "react";

type Scheme = "light" | "dark";

const Ctx = createContext({ colorScheme: "light" as Scheme, toggle: () => {} });

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [colorScheme, setColorScheme] = useState<Scheme>(
    () => (localStorage.getItem("color_scheme") as Scheme) || "light"
  );

  useEffect(() => {
    localStorage.setItem("color_scheme", colorScheme);
  }, [colorScheme]);

  const toggle = () => setColorScheme((s) => (s === "light" ? "dark" : "light"));

  return <Ctx.Provider value={{ colorScheme, toggle }}>{children}</Ctx.Provider>;
}

export const useThemeMode = () => useContext(Ctx);
