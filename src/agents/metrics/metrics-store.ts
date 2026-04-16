import { mkdirSync } from "node:fs";
import path from "node:path";
import type { DatabaseSync, StatementSync } from "node:sqlite";
import { requireNodeSqlite } from "../../infra/node-sqlite.js";
import type { SessionOutcome } from "./outcome-classifier.js";

export type SessionMetricRecord = {
  sessionId: string;
  agentId: string;
  outcome: SessionOutcome;
  messageCount: number;
  durationMs?: number;
  turnCount: number;
  timestamp: number;
};

export type SessionMetricRow = SessionMetricRecord;

export type MetricsSummary = {
  totalSessions: number;
  successRate: number;
  failRate: number;
  partialRate: number;
  unknownRate: number;
};

export class MetricsStore {
  private db: DatabaseSync;
  private insertStmt: StatementSync;
  private queryByAgentStmt: StatementSync;
  private summaryStmt: StatementSync;

  constructor(dbPath: string) {
    mkdirSync(path.dirname(dbPath), { recursive: true });
    const { DatabaseSync } = requireNodeSqlite();
    this.db = new DatabaseSync(dbPath);
    this.db.exec("PRAGMA journal_mode=WAL");
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS session_metrics (
        session_id TEXT PRIMARY KEY,
        agent_id TEXT NOT NULL,
        outcome TEXT NOT NULL,
        message_count INTEGER NOT NULL,
        duration_ms INTEGER,
        turn_count INTEGER NOT NULL,
        timestamp INTEGER NOT NULL
      )
    `);

    this.insertStmt = this.db.prepare(`
      INSERT OR REPLACE INTO session_metrics
        (session_id, agent_id, outcome, message_count, duration_ms, turn_count, timestamp)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `);

    this.queryByAgentStmt = this.db.prepare(
      "SELECT * FROM session_metrics WHERE agent_id = ? ORDER BY timestamp DESC",
    );

    this.summaryStmt = this.db.prepare(`
      SELECT
        COUNT(*) as total,
        SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) as success_count,
        SUM(CASE WHEN outcome = 'fail' THEN 1 ELSE 0 END) as fail_count,
        SUM(CASE WHEN outcome = 'partial' THEN 1 ELSE 0 END) as partial_count,
        SUM(CASE WHEN outcome = 'unknown' THEN 1 ELSE 0 END) as unknown_count
      FROM session_metrics
      WHERE agent_id = ?
    `);
  }

  recordSession(record: SessionMetricRecord): void {
    this.insertStmt.run(
      record.sessionId,
      record.agentId,
      record.outcome,
      record.messageCount,
      record.durationMs ?? null,
      record.turnCount,
      record.timestamp,
    );
  }

  querySessions(opts: { agentId: string }): SessionMetricRow[] {
    const rows = this.queryByAgentStmt.all(opts.agentId) as Array<Record<string, unknown>>;
    return rows.map((row) => ({
      sessionId: row.session_id as string,
      agentId: row.agent_id as string,
      outcome: row.outcome as SessionOutcome,
      messageCount: Number(row.message_count),
      durationMs: row.duration_ms != null ? Number(row.duration_ms) : undefined,
      turnCount: Number(row.turn_count),
      timestamp: Number(row.timestamp),
    }));
  }

  summary(opts: { agentId: string }): MetricsSummary {
    const row = this.summaryStmt.get(opts.agentId) as Record<string, unknown>;
    const total = Number(row.total);
    if (total === 0) {
      return { totalSessions: 0, successRate: 0, failRate: 0, partialRate: 0, unknownRate: 0 };
    }
    return {
      totalSessions: total,
      successRate: Number(row.success_count) / total,
      failRate: Number(row.fail_count) / total,
      partialRate: Number(row.partial_count) / total,
      unknownRate: Number(row.unknown_count) / total,
    };
  }

  close(): void {
    this.db.close();
  }
}
