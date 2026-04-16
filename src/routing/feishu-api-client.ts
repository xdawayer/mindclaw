import type {
  FeishuApiUser,
  FeishuApiDepartment,
  FeishuDirectoryDeps,
} from "./feishu-directory-adapter.js";

export type FeishuApiConfig = {
  appId: string;
  appSecret: string;
  baseUrl: string;
};

export type HttpFetch = (url: string, init?: RequestInit) => Promise<Response>;

type FeishuApiClient = {
  fetchUsers: () => Promise<FeishuApiUser[]>;
  fetchDepartments: () => Promise<FeishuApiDepartment[]>;
};

async function acquireTenantToken(config: FeishuApiConfig, fetch: HttpFetch): Promise<string> {
  const resp = await fetch(`${config.baseUrl}/auth/v3/tenant_access_token/internal`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      app_id: config.appId,
      app_secret: config.appSecret,
    }),
  });

  if (!resp.ok) {
    throw new Error("Failed to acquire Feishu tenant token");
  }

  const data = (await resp.json()) as { code: number; tenant_access_token?: string };
  if (data.code !== 0 || !data.tenant_access_token) {
    throw new Error("Failed to acquire Feishu tenant token");
  }

  return data.tenant_access_token;
}

async function fetchWithAuth<T>(url: string, token: string, fetch: HttpFetch): Promise<T[]> {
  const resp = await fetch(url, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  });

  if (!resp.ok) {
    throw new Error(`Feishu API request failed: ${resp.status}`);
  }

  const data = (await resp.json()) as { code: number; data?: { items?: T[] } };
  return data.data?.items ?? [];
}

export function createFeishuApiClient(config: FeishuApiConfig, fetch: HttpFetch): FeishuApiClient {
  let cachedToken: string | null = null;

  async function getToken(): Promise<string> {
    if (cachedToken) {
      return cachedToken;
    }
    cachedToken = await acquireTenantToken(config, fetch);
    return cachedToken;
  }

  return {
    async fetchUsers(): Promise<FeishuApiUser[]> {
      const token = await getToken();
      return fetchWithAuth<FeishuApiUser>(
        `${config.baseUrl}/contact/v3/users?page_size=50`,
        token,
        fetch,
      );
    },
    async fetchDepartments(): Promise<FeishuApiDepartment[]> {
      const token = await getToken();
      return fetchWithAuth<FeishuApiDepartment>(
        `${config.baseUrl}/contact/v3/departments?page_size=50`,
        token,
        fetch,
      );
    },
  };
}

export function buildFeishuDirectoryDeps(
  config: FeishuApiConfig,
  fetch: HttpFetch,
): FeishuDirectoryDeps {
  const client = createFeishuApiClient(config, fetch);
  return {
    fetchUsers: client.fetchUsers,
    fetchDepartments: client.fetchDepartments,
  };
}
