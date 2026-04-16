// Feishu directory API adapter — fetches raw Feishu API data and
// transforms it into the FeishuUserInfo shape used by the binding mapper.

import type { FeishuUserInfo } from "./feishu-directory-mapping.js";

/** Raw Feishu API response shape for a user. */
export type FeishuApiUser = {
  user_id: string;
  name: string;
  department_ids: string[];
  job_title?: string;
};

/** Raw Feishu API response shape for a department. */
export type FeishuApiDepartment = {
  department_id: string;
  name: string;
  parent_department_id?: string;
};

export type FeishuDirectoryDeps = {
  fetchUsers: () => Promise<FeishuApiUser[]>;
  fetchDepartments: () => Promise<FeishuApiDepartment[]>;
};

/** Fetch and transform Feishu directory into FeishuUserInfo[]. */
export async function fetchFeishuDirectory(deps: FeishuDirectoryDeps): Promise<FeishuUserInfo[]> {
  const [users, departments] = await Promise.all([deps.fetchUsers(), deps.fetchDepartments()]);

  // Build a lookup map from department_id to department name.
  const deptMap = new Map<string, string>(departments.map((d) => [d.department_id, d.name]));

  return users.map((u) => {
    const info: FeishuUserInfo = {
      userId: u.user_id,
      name: u.name,
      department: deptMap.get(u.department_ids[0] ?? "") ?? "",
    };
    if (u.job_title) {
      info.jobTitle = u.job_title;
    }
    return info;
  });
}
