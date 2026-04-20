import type { RouteRecordRaw } from "vue-router";

/**
 * 路由级页面统一采用懒加载。
 * 这样可以把登录页、详情页和统计页拆成独立 chunk，减少首屏体积。
 */
const LoginPage = () => import("@/pages/LoginPage.vue");
const DashboardPage = () => import("@/pages/DashboardPage.vue");
const RecordsPage = () => import("@/pages/RecordsPage.vue");
const RecordDetailPage = () => import("@/pages/RecordDetailPage.vue");
const PartsPage = () => import("@/pages/PartsPage.vue");
const DevicesPage = () => import("@/pages/DevicesPage.vue");
const StatisticsPage = () => import("@/pages/StatisticsPage.vue");
const StatisticsGalleryPage = () => import("@/pages/StatisticsGalleryPage.vue");
const SettingsPage = () => import("@/pages/SettingsPage.vue");

export const routeNames = {
  login: "login",
  dashboard: "dashboard",
  records: "records",
  recordDetail: "record-detail",
  parts: "parts",
  devices: "devices",
  statistics: "statistics",
  statisticsGallery: "statistics-gallery",
  settings: "settings",
} as const;

export interface AppNavigationItem {
  readonly name: keyof typeof routeNames;
  readonly title: string;
  readonly icon: string;
}

export const appNavigationItems: AppNavigationItem[] = [
  { name: "dashboard", title: "仪表盘", icon: "DataBoard" },
  { name: "records", title: "检测记录", icon: "Tickets" },
  { name: "parts", title: "零件管理", icon: "CollectionTag" },
  { name: "devices", title: "设备管理", icon: "Monitor" },
  { name: "statistics", title: "统计分析", icon: "TrendCharts" },
  { name: "settings", title: "系统设置", icon: "Setting" },
];

export const routes: RouteRecordRaw[] = [
  {
    path: "/",
    redirect: "/dashboard",
  },
  {
    path: "/login",
    name: routeNames.login,
    component: LoginPage,
    meta: {
      title: "登录",
      requiresAuth: false,
      useShell: false,
    },
  },
  {
    path: "/dashboard",
    name: routeNames.dashboard,
    component: DashboardPage,
    meta: {
      title: "仪表盘",
      requiresAuth: true,
    },
  },
  {
    path: "/records",
    name: routeNames.records,
    component: RecordsPage,
    meta: {
      title: "检测记录",
      requiresAuth: true,
    },
  },
  {
    path: "/records/:id",
    name: routeNames.recordDetail,
    component: RecordDetailPage,
    meta: {
      title: "检测详情",
      requiresAuth: true,
    },
    props: true,
  },
  {
    path: "/parts",
    name: routeNames.parts,
    component: PartsPage,
    meta: {
      title: "零件管理",
      requiresAuth: true,
    },
  },
  {
    path: "/devices",
    name: routeNames.devices,
    component: DevicesPage,
    meta: {
      title: "设备管理",
      requiresAuth: true,
    },
  },
  {
    path: "/statistics",
    name: routeNames.statistics,
    component: StatisticsPage,
    meta: {
      title: "统计分析",
      requiresAuth: true,
    },
  },
  {
    path: "/statistics/gallery",
    name: routeNames.statisticsGallery,
    component: StatisticsGalleryPage,
    meta: {
      title: "样本图库",
      requiresAuth: true,
    },
  },
  {
    path: "/settings",
    name: routeNames.settings,
    component: SettingsPage,
    meta: {
      title: "系统设置",
      requiresAuth: true,
    },
  },
];
