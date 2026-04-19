const authTokenStorageKey = "yunduan:auth-token";

/**
 * 从本地存储读取当前登录令牌。
 * 浏览器环境不可用时返回空字符串，避免 SSR 或测试场景报错。
 */
export function getStoredAuthToken(): string {
  if (typeof window === "undefined") {
    return "";
  }
  return window.localStorage.getItem(authTokenStorageKey) ?? "";
}

/**
 * 持久化最新登录令牌。
 */
export function setStoredAuthToken(token: string): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(authTokenStorageKey, token);
}

/**
 * 清除本地已保存的登录令牌。
 */
export function clearStoredAuthToken(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(authTokenStorageKey);
}
