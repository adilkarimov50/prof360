import {
  IconLayoutDashboard,
  IconUsers,
  IconScale,
  IconRobot,
  IconFileText,
  IconUpload,
  IconChartBar,
  IconShieldLock,
  IconSettings,
  IconDatabase,
  IconUserCog,
  IconClipboardList,
  IconReportAnalytics,
  IconChecklist,
  IconMap2,
  IconScaleOutline,
  IconBuildingCommunity,
} from "@tabler/icons-react";

export interface NavItem {
  to: string;
  label: string;
  icon: typeof IconLayoutDashboard;
  end?: boolean;
  roles?: string[];
}

export const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Дашборд", icon: IconLayoutDashboard, end: true },
  { to: "/persons", label: "Лица и риск-профили", icon: IconUsers },
  { to: "/analytics", label: "Аналитика", icon: IconChartBar },
  { to: "/analytics/unified", label: "Сводная картина области", icon: IconMap2 },
  { to: "/localities", label: "Криминологические паспорта", icon: IconBuildingCommunity },
  { to: "/adm-blocks", label: "Адм. практика: личность / дороги", icon: IconScaleOutline },
  { to: "/legal", label: "Нормативная база", icon: IconScale },
  { to: "/ai", label: "ИИ-консультант", icon: IconRobot },
  { to: "/spravka", label: "Справки и акты", icon: IconFileText },
  { to: "/commission", label: "Комиссия по профилактике", icon: IconClipboardList },
  { to: "/commission-sessions", label: "Заседания МВК / Поручения", icon: IconChecklist },
  { to: "/commission-analytics", label: "Аналитика МВК", icon: IconReportAnalytics },
  { to: "/quality", label: "Качество данных", icon: IconDatabase, roles: ["admin", "analyst", "oblast_prosecutor", "deputy_prosecutor"] },
  { to: "/upload", label: "Загрузка Excel", icon: IconUpload, roles: ["admin", "analyst"] },
  { to: "/admin", label: "Администрирование", icon: IconUserCog, roles: ["admin"] },
  { to: "/audit", label: "Аудит и DLP", icon: IconShieldLock, roles: ["admin", "security_auditor", "oblast_prosecutor"] },
];

export function navForRole(role: string | undefined): NavItem[] {
  return NAV_ITEMS.filter((item) => !item.roles || (role && item.roles.includes(role)));
}

export function canAccess(role: string | undefined, roles?: string[]): boolean {
  if (!roles) return true;
  return !!role && roles.includes(role);
}
