import path from "node:path";
import { MetricsStore } from "./metrics-store.js";

export class MetricsStoreRegistry {
  private stores = new Map<string, MetricsStore>();
  private baseDir: string;

  constructor(baseDir: string) {
    this.baseDir = baseDir;
  }

  getStore(agentId: string): MetricsStore {
    const existing = this.stores.get(agentId);
    if (existing) {
      return existing;
    }

    const dbPath = path.join(this.baseDir, agentId, "metrics.sqlite");
    const store = new MetricsStore(dbPath);
    this.stores.set(agentId, store);
    return store;
  }

  closeAll(): void {
    for (const store of this.stores.values()) {
      store.close();
    }
    this.stores.clear();
  }
}
