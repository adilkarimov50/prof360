import axios from "axios";

const api = axios.create({ baseURL: "/api" });

let refreshing: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const rt = localStorage.getItem("refresh_token");
  if (!rt) return null;
  try {
    const { data } = await axios.post("/api/auth/refresh", { refresh_token: rt });
    localStorage.setItem("access_token", data.access_token);
    if (data.refresh_token) localStorage.setItem("refresh_token", data.refresh_token);
    return data.access_token;
  } catch {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    return null;
  }
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      if (!refreshing) refreshing = refreshAccessToken().finally(() => { refreshing = null; });
      const token = await refreshing;
      if (token) {
        original.headers.Authorization = `Bearer ${token}`;
        return api(original);
      }
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export function saveTokens(access: string, refresh?: string) {
  localStorage.setItem("access_token", access);
  if (refresh) localStorage.setItem("refresh_token", refresh);
}

export function clearTokens() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

export default api;

// --- Типы ---
export interface MeUser {
  id: number;
  username: string;
  full_name: string;
  role: string;
  district: string | null;
  can_export: boolean;
  can_access_minors: boolean;
  totp_enabled: boolean;
  must_change_password?: boolean;
}

export interface PersonShort {
  id: number;
  fio: string;
  iin_masked: string;
  district: string | null;
  risk_score: number;
  risk_level: string;
}

export interface Norm {
  id: number;
  act: string;
  act_number: string | null;
  article: string | null;
  point: string | null;
  title: string | null;
  text_ru: string | null;
  status: string;
  edition_start: string | null;
  category: string | null;
  subject: string | null;
  measure: string | null;
  source_url: string | null;
}

export const ROLE_LABELS: Record<string, string> = {
  oblast_prosecutor: "Прокурор области",
  deputy_prosecutor: "Заместитель прокурора области",
  department_head: "Начальник управления",
  analyst: "Прокурор-аналитик",
  district_prosecutor: "Прокурор района",
  osint_user: "OSINT-пользователь",
  admin: "Администратор системы",
  security_auditor: "Аудитор безопасности",
};

export const RISK_COLORS: Record<string, string> = {
  Низкий: "green",
  Средний: "yellow",
  Высокий: "orange",
  Критический: "red",
};
