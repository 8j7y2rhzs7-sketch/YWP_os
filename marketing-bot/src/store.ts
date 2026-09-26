import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import type { MarketingDraft } from "./types.js";

export class DraftStore {
  private readonly file: string;

  constructor(dataDirectory: string) {
    this.file = path.join(dataDirectory, "drafts.json");
  }

  private async readAll(): Promise<MarketingDraft[]> {
    try {
      return JSON.parse(await readFile(this.file, "utf8")) as MarketingDraft[];
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return [];
      throw error;
    }
  }

  private async writeAll(drafts: MarketingDraft[]): Promise<void> {
    await mkdir(path.dirname(this.file), { recursive: true });
    await writeFile(this.file, `${JSON.stringify(drafts, null, 2)}\n`, "utf8");
  }

  async list(): Promise<MarketingDraft[]> {
    return (await this.readAll()).sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  }

  async get(id: string): Promise<MarketingDraft | undefined> {
    return (await this.readAll()).find((draft) => draft.id === id);
  }

  async save(draft: MarketingDraft): Promise<MarketingDraft> {
    const drafts = await this.readAll();
    const index = drafts.findIndex((item) => item.id === draft.id);
    if (index >= 0) drafts[index] = draft;
    else drafts.push(draft);
    await this.writeAll(drafts);
    return draft;
  }

  async findByCardId(cardId: string): Promise<MarketingDraft | undefined> {
    return (await this.readAll()).find((draft) => draft.cardId === cardId);
  }
}
