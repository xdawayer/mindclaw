# Upstream Sync

每天检查 `openclaw/openclaw` 的更新，评估差异性与兼容性，有变化时开 PR，通过飞书通知王志彪 (`ou_3ce0dce02872c344a4e244a1837ebced`)。

## 运行方式

GitHub Actions workflow `.github/workflows/upstream-sync.yml`：
- 定时：每天 UTC 01:00（北京 09:00）
- 手动：Actions 面板 "Run workflow"

## 工作流程

1. 读取 `base.sha` 作为上次已同步的上游基线
2. `git fetch upstream main` 取最新 HEAD
3. `evaluate.sh` 计算：
   - 上游新 commits 数 / 上游改过的文件
   - 本地 fork 相对 base 改过的文件
   - 交集 = **可能冲突**（需人工确认）
   - 差集（纯上游）= 理论可直合并
4. 有更新时 `create-pr.sh`：
   - 建分支 `upstream-sync/YYYY-MM-DD-<short>`
   - 尝试 `git merge upstream/main --allow-unrelated-histories`
     - 成功 → merge commit + 推进 `base.sha` → 开 PR（可直接合并）
     - 冲突 → 带 conflict markers 的 commit 进分支 → 开 PR（需人工解决）
5. `notify-feishu.sh` 推送消息给目标 open_id

## 所需 Secrets / Variables

Repo Settings → Secrets and variables → Actions：

| 名称 | 类型 | 说明 |
|---|---|---|
| `FEISHU_APP_ID` | Secret | 飞书自建 App 的 App ID |
| `FEISHU_APP_SECRET` | Secret | 飞书自建 App 的 App Secret |

飞书 App 需开 `im:message` 权限（发送消息给用户）。没配这两个 secret 时，workflow 仍会跑，但飞书通知步骤 skip（只开 PR）。

目标用户 open_id 直接写在 workflow 里：`ou_3ce0dce02872c344a4e244a1837ebced`。

## 基线推进

`base.sha` 只有在 sync PR 被 merge 到 main 时才前进（PR 的最后一个 commit 会写入新值）。这样未合并 / 回滚 / 放弃的同步不会污染基线。

手动前进（例如跳过某次同步）：编辑 `.upstream-sync/base.sha` 为目标上游 SHA，直接 commit 到 main。
