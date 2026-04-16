import { describe, expect, it } from "vitest";
import { fetchFeishuDirectory, type FeishuDirectoryDeps } from "./feishu-directory-adapter.js";

function makeDeps(overrides: Partial<FeishuDirectoryDeps> = {}): FeishuDirectoryDeps {
  return {
    fetchUsers: async () => [],
    fetchDepartments: async () => [],
    ...overrides,
  };
}

describe("fetchFeishuDirectory", () => {
  it("transforms single user with one department correctly", async () => {
    const deps = makeDeps({
      fetchUsers: async () => [{ user_id: "u1", name: "Alice", department_ids: ["d1"] }],
      fetchDepartments: async () => [{ department_id: "d1", name: "Engineering" }],
    });
    const result = await fetchFeishuDirectory(deps);
    expect(result).toEqual([{ userId: "u1", name: "Alice", department: "Engineering" }]);
  });

  it("resolves department_id to department name", async () => {
    const deps = makeDeps({
      fetchUsers: async () => [{ user_id: "u1", name: "Bob", department_ids: ["d2"] }],
      fetchDepartments: async () => [
        { department_id: "d1", name: "Engineering" },
        { department_id: "d2", name: "Marketing" },
      ],
    });
    const result = await fetchFeishuDirectory(deps);
    expect(result).toEqual([{ userId: "u1", name: "Bob", department: "Marketing" }]);
  });

  it("user with multiple departments uses the first one", async () => {
    const deps = makeDeps({
      fetchUsers: async () => [{ user_id: "u1", name: "Carol", department_ids: ["d2", "d1"] }],
      fetchDepartments: async () => [
        { department_id: "d1", name: "Engineering" },
        { department_id: "d2", name: "Sales" },
      ],
    });
    const result = await fetchFeishuDirectory(deps);
    expect(result).toEqual([{ userId: "u1", name: "Carol", department: "Sales" }]);
  });

  it("user with unknown department_id gets empty department string", async () => {
    const deps = makeDeps({
      fetchUsers: async () => [{ user_id: "u1", name: "Dave", department_ids: ["d999"] }],
      fetchDepartments: async () => [{ department_id: "d1", name: "Engineering" }],
    });
    const result = await fetchFeishuDirectory(deps);
    expect(result).toEqual([{ userId: "u1", name: "Dave", department: "" }]);
  });

  it("handles empty user list", async () => {
    const deps = makeDeps({
      fetchUsers: async () => [],
      fetchDepartments: async () => [{ department_id: "d1", name: "Engineering" }],
    });
    const result = await fetchFeishuDirectory(deps);
    expect(result).toEqual([]);
  });

  it("includes job_title when present", async () => {
    const deps = makeDeps({
      fetchUsers: async () => [
        {
          user_id: "u1",
          name: "Eve",
          department_ids: ["d1"],
          job_title: "Staff Engineer",
        },
      ],
      fetchDepartments: async () => [{ department_id: "d1", name: "Engineering" }],
    });
    const result = await fetchFeishuDirectory(deps);
    expect(result).toEqual([
      {
        userId: "u1",
        name: "Eve",
        department: "Engineering",
        jobTitle: "Staff Engineer",
      },
    ]);
  });

  it("user with empty department_ids gets empty department string", async () => {
    const deps = makeDeps({
      fetchUsers: async () => [{ user_id: "u1", name: "Ghost", department_ids: [] }],
      fetchDepartments: async () => [{ department_id: "d1", name: "Engineering" }],
    });
    const result = await fetchFeishuDirectory(deps);
    expect(result).toEqual([{ userId: "u1", name: "Ghost", department: "" }]);
  });

  it("propagates fetch error (does not swallow)", async () => {
    const deps = makeDeps({
      fetchUsers: async () => {
        throw new Error("API rate limited");
      },
    });
    await expect(fetchFeishuDirectory(deps)).rejects.toThrow("API rate limited");
  });
});
