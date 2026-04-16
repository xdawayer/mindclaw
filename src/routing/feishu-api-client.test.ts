import { describe, expect, it, vi, beforeEach } from "vitest";
import {
  createFeishuApiClient,
  buildFeishuDirectoryDeps,
  type FeishuApiConfig,
  type HttpFetch,
} from "./feishu-api-client.js";

describe("feishu-api-client", () => {
  const config: FeishuApiConfig = {
    appId: "cli_test123",
    appSecret: "secret456",
    baseUrl: "https://open.feishu.cn/open-apis",
  };

  let mockFetch: HttpFetch;

  beforeEach(() => {
    mockFetch = vi.fn();
  });

  describe("createFeishuApiClient", () => {
    it("fetches tenant access token before API calls", async () => {
      vi.mocked(mockFetch)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            code: 0,
            tenant_access_token: "t-token123",
            expire: 7200,
          }),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            code: 0,
            data: { items: [] },
          }),
        } as Response);

      const client = createFeishuApiClient(config, mockFetch);
      await client.fetchUsers();

      // First call: token request
      expect(mockFetch).toHaveBeenCalledWith(
        `${config.baseUrl}/auth/v3/tenant_access_token/internal`,
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            app_id: config.appId,
            app_secret: config.appSecret,
          }),
        }),
      );
    });

    it("passes tenant token in Authorization header for user list", async () => {
      vi.mocked(mockFetch)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            code: 0,
            tenant_access_token: "t-token123",
            expire: 7200,
          }),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            code: 0,
            data: {
              items: [{ user_id: "u1", name: "Alice", department_ids: ["d1"] }],
            },
          }),
        } as Response);

      const client = createFeishuApiClient(config, mockFetch);
      const users = await client.fetchUsers();

      expect(users).toEqual([{ user_id: "u1", name: "Alice", department_ids: ["d1"] }]);

      // Second call should have bearer token
      const secondCall = vi.mocked(mockFetch).mock.calls[1];
      expect(secondCall[1]?.headers).toMatchObject({
        Authorization: "Bearer t-token123",
      });
    });

    it("throws on token acquisition failure", async () => {
      vi.mocked(mockFetch).mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ code: 10003, msg: "invalid app_secret" }),
      } as Response);

      const client = createFeishuApiClient(config, mockFetch);
      await expect(client.fetchUsers()).rejects.toThrow("Failed to acquire Feishu tenant token");
    });

    it("fetches departments list", async () => {
      vi.mocked(mockFetch)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            code: 0,
            tenant_access_token: "t-token123",
            expire: 7200,
          }),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            code: 0,
            data: {
              items: [
                { department_id: "d1", name: "Engineering" },
                { department_id: "d2", name: "Sales" },
              ],
            },
          }),
        } as Response);

      const client = createFeishuApiClient(config, mockFetch);
      const depts = await client.fetchDepartments();

      expect(depts).toEqual([
        { department_id: "d1", name: "Engineering" },
        { department_id: "d2", name: "Sales" },
      ]);
    });

    it("reuses cached token for sequential calls", async () => {
      // Token response (only once)
      vi.mocked(mockFetch)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            code: 0,
            tenant_access_token: "t-cached",
            expire: 7200,
          }),
        } as Response)
        // First API call
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ code: 0, data: { items: [] } }),
        } as Response)
        // Second API call (no new token request)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ code: 0, data: { items: [] } }),
        } as Response);

      const client = createFeishuApiClient(config, mockFetch);
      await client.fetchUsers();
      await client.fetchDepartments();

      // Should be 3 calls total: 1 token + 2 API, not 4 (2 tokens + 2 API)
      expect(mockFetch).toHaveBeenCalledTimes(3);
    });
  });

  describe("buildFeishuDirectoryDeps", () => {
    it("returns FeishuDirectoryDeps from config", () => {
      const deps = buildFeishuDirectoryDeps(config, mockFetch);
      expect(typeof deps.fetchUsers).toBe("function");
      expect(typeof deps.fetchDepartments).toBe("function");
    });
  });
});
