import type {ClearBlockMetadata} from "./types";

export interface SyncedUserRule {
  filterText: string;
  metadata: ClearBlockMetadata;
}

export interface SyncManifest {
  version: 1;
  chunkCount: number;
  updatedAt: number;
}

export interface SyncSnapshot {
  version: 1;
  updatedAt: number;
  rules: SyncedUserRule[];
}

const FORMAT_VERSION = 1 as const;
const CHUNK_BYTES = 4_500;
const MAX_SNAPSHOT_BYTES = 60_000;

function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

function base64ToBytes(value: string): Uint8Array {
  const binary = atob(value);
  return Uint8Array.from(binary, character => character.charCodeAt(0));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isMetadata(value: unknown): value is ClearBlockMetadata {
  if (!isRecord(value)) return false;
  if (value.kind !== "allowlist" && value.kind !== "element") return false;
  if (typeof value.value !== "string" || typeof value.hostname !== "string") return false;
  if (!value.value || !value.hostname || !Number.isFinite(value.createdAt)) return false;
  return value.kind === "element" || value.scope === "site" || value.scope === "page";
}

function isSyncedRule(value: unknown): value is SyncedUserRule {
  return isRecord(value)
    && typeof value.filterText === "string"
    && value.filterText.length > 0
    && value.filterText.length <= 4_096
    && isMetadata(value.metadata);
}

export function encodeSyncSnapshot(
  rules: SyncedUserRule[],
  updatedAt = Date.now()
): {manifest: SyncManifest; chunks: string[]} {
  const bytes = new TextEncoder().encode(JSON.stringify({
    version: FORMAT_VERSION,
    updatedAt,
    rules
  } satisfies SyncSnapshot));
  if (bytes.byteLength > MAX_SNAPSHOT_BYTES) {
    throw new Error("ClearBlock user rules exceed the Chrome Sync storage limit.");
  }

  const chunks: string[] = [];
  for (let offset = 0; offset < bytes.byteLength; offset += CHUNK_BYTES) {
    chunks.push(bytesToBase64(bytes.subarray(offset, offset + CHUNK_BYTES)));
  }
  return {
    manifest: {version: FORMAT_VERSION, chunkCount: chunks.length, updatedAt},
    chunks
  };
}

export function decodeSyncSnapshot(manifest: unknown, chunks: unknown[]): SyncSnapshot {
  if (!isRecord(manifest)
    || manifest.version !== FORMAT_VERSION
    || !Number.isInteger(manifest.chunkCount)
    || Number(manifest.chunkCount) < 1
    || !Number.isFinite(manifest.updatedAt)
    || chunks.length !== manifest.chunkCount
    || chunks.some(chunk => typeof chunk !== "string")) {
    throw new Error("ClearBlock sync data is incomplete or unsupported.");
  }

  let parsed: unknown;
  try {
    const byteChunks = (chunks as string[]).map(base64ToBytes);
    const byteLength = byteChunks.reduce((total, chunk) => total + chunk.byteLength, 0);
    if (byteLength > MAX_SNAPSHOT_BYTES) throw new Error("too large");
    const bytes = new Uint8Array(byteLength);
    let offset = 0;
    for (const chunk of byteChunks) {
      bytes.set(chunk, offset);
      offset += chunk.byteLength;
    }
    parsed = JSON.parse(new TextDecoder("utf-8", {fatal: true}).decode(bytes));
  } catch {
    throw new Error("ClearBlock sync data is invalid.");
  }

  if (!isRecord(parsed)
    || parsed.version !== FORMAT_VERSION
    || parsed.updatedAt !== manifest.updatedAt
    || !Array.isArray(parsed.rules)
    || !parsed.rules.every(isSyncedRule)) {
    throw new Error("ClearBlock sync data is invalid.");
  }
  return parsed as unknown as SyncSnapshot;
}

export function mergeSyncedRules(
  first: SyncedUserRule[],
  second: SyncedUserRule[]
): SyncedUserRule[] {
  const merged = new Map<string, SyncedUserRule>();
  for (const rule of [...first, ...second]) {
    const existing = merged.get(rule.filterText);
    if (!existing || rule.metadata.createdAt > existing.metadata.createdAt) {
      merged.set(rule.filterText, rule);
    }
  }
  return [...merged.values()];
}
