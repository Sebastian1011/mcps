declare function importScripts(...urls: string[]): void;
importScripts("vendor/ewe-api.js");

import type * as Eyeo from "@eyeo/webext-ad-filtering-solution";
import recommendations from "../rules/recommendations.json";
import {
  canonicalPageUrl,
  classifyUserFilters,
  createAllowlistRule,
  createElementRule
} from "./shared/filters";
import {
  decodeSyncSnapshot,
  encodeSyncSnapshot,
  mergeSyncedRules,
  type SyncedUserRule,
  type SyncSnapshot
} from "./shared/sync";
import type {
  ClearBlockMetadata,
  OptionsState,
  PopupState,
  RuntimeRequest,
  RuntimeResponse,
  SubscriptionStatus
} from "./shared/types";

declare const EWE: typeof Eyeo;

interface ReportingApi {
  onBlockableItem: {
    addListener(listener: (item: Eyeo.BlockableItem) => void): void;
  };
}

type SubscriptionApi = typeof EWE.subscriptions & {
  add(url: string): Promise<void>;
  sync(url?: string): Promise<void>;
};

interface CounterState {
  total: number;
  tabs: Record<string, number>;
}

const COUNTER_STORAGE_KEY = "clearBlockTotalCount";
const USER_SYNC_ENABLED_KEY = "clearBlockUserSyncEnabled";
const SYNC_MANIFEST_KEY = "clearBlockUserRulesManifest";
const SYNC_CHUNK_PREFIX = "clearBlockUserRulesChunk:";
let counters: CounterState = {total: 0, tabs: {}};
let countersLoaded: Promise<void> | undefined;
let counterFlushTimer: number | undefined;
let userSyncEnabled = false;
let userSyncError: string | null = null;
let syncChangeTimer: number | undefined;

function loadCounters(): Promise<void> {
  countersLoaded ??= Promise.all([
    chrome.storage.local.get(COUNTER_STORAGE_KEY),
    chrome.storage.session.get("clearBlockTabCounts")
  ]).then(([local, session]) => {
    counters.total = Number(local[COUNTER_STORAGE_KEY]) || 0;
    const tabs = session.clearBlockTabCounts;
    counters.tabs = tabs && typeof tabs === "object" ? tabs as Record<string, number> : {};
  });
  return countersLoaded;
}

async function flushCounters(): Promise<void> {
  if (counterFlushTimer !== undefined) {
    clearTimeout(counterFlushTimer);
    counterFlushTimer = undefined;
  }
  await Promise.all([
    chrome.storage.local.set({[COUNTER_STORAGE_KEY]: counters.total}),
    chrome.storage.session.set({clearBlockTabCounts: counters.tabs})
  ]);
}

function scheduleCounterFlush(): void {
  if (counterFlushTimer !== undefined) return;
  counterFlushTimer = setTimeout(() => void flushCounters(), 1000) as unknown as number;
}

function isBlockedItem(item: Eyeo.BlockableItem): boolean {
  if (!item.filter) return false;
  if (["allowing", "unmatched"].includes(item.matchInfo.method)) return false;
  return item.filter.type !== "allowing";
}

function recordBlockedItem(item: Eyeo.BlockableItem): void {
  const tabId = "tabId" in item.request ? item.request.tabId : -1;
  if (!isBlockedItem(item) || typeof tabId !== "number" || tabId < 0) return;
  void loadCounters().then(() => {
    counters.total += 1;
    counters.tabs[String(tabId)] = (counters.tabs[String(tabId)] ?? 0) + 1;
    scheduleCounterFlush();
  });
}

(EWE.reporting as unknown as ReportingApi).onBlockableItem.addListener(recordBlockedItem);

const engineReady = EWE.start({
  name: "ClearBlock",
  version: chrome.runtime.getManifest().version,
  lightningSnippets: true,
  bundledSubscriptions: recommendations,
  bundledSubscriptionsPath: "subscriptions"
}).then(async () => {
  const subscriptions = EWE.subscriptions as unknown as SubscriptionApi;
  for (const recommendation of recommendations) {
    if (!await subscriptions.has(recommendation.url)) {
      await subscriptions.add(recommendation.url);
    }
  }
  EWE.signalStartupComplete();
});

interface ManagedFilter {
  text: string;
  metadata?: {clearBlock?: ClearBlockMetadata};
}

async function getManagedRules(): Promise<SyncedUserRule[]> {
  const filters = await EWE.filters.getUserFilters() as ManagedFilter[];
  return filters.flatMap(filter => filter.metadata?.clearBlock
    ? [{filterText: filter.text, metadata: filter.metadata.clearBlock}]
    : []);
}

function syncChunkKey(index: number): string {
  return `${SYNC_CHUNK_PREFIX}${index}`;
}

async function readCloudSnapshot(): Promise<SyncSnapshot | undefined> {
  const storedManifest = await chrome.storage.sync.get(SYNC_MANIFEST_KEY);
  const manifest = storedManifest[SYNC_MANIFEST_KEY] as {chunkCount?: unknown} | undefined;
  if (!manifest) return undefined;
  if (!Number.isInteger(manifest.chunkCount)
    || Number(manifest.chunkCount) < 1
    || Number(manifest.chunkCount) > 14) {
    throw new Error("ClearBlock sync data is incomplete or unsupported.");
  }
  const keys = Array.from({length: Number(manifest.chunkCount)}, (_, index) => syncChunkKey(index));
  const storedChunks = await chrome.storage.sync.get(keys);
  return decodeSyncSnapshot(manifest, keys.map(key => storedChunks[key]));
}

async function writeCloudSnapshot(rules?: SyncedUserRule[]): Promise<void> {
  rules ??= await getManagedRules();
  const previous = await chrome.storage.sync.get(SYNC_MANIFEST_KEY);
  const previousCount = Number((previous[SYNC_MANIFEST_KEY] as {chunkCount?: unknown} | undefined)?.chunkCount) || 0;
  const {manifest, chunks} = encodeSyncSnapshot(rules);
  const values: Record<string, unknown> = {[SYNC_MANIFEST_KEY]: manifest};
  chunks.forEach((chunk, index) => values[syncChunkKey(index)] = chunk);
  await chrome.storage.sync.set(values);

  const staleKeys = Array.from(
    {length: Math.max(0, previousCount - chunks.length)},
    (_, index) => syncChunkKey(chunks.length + index)
  );
  if (staleKeys.length) await chrome.storage.sync.remove(staleKeys);
}

function sameManagedRule(first: SyncedUserRule, second: SyncedUserRule): boolean {
  return first.filterText === second.filterText
    && JSON.stringify(first.metadata) === JSON.stringify(second.metadata);
}

function validateManagedRule(rule: SyncedUserRule): void {
  const expected = rule.metadata.kind === "allowlist" && rule.metadata.scope
    ? createAllowlistRule(rule.metadata.scope, rule.metadata.value).filterText
    : createElementRule(`https://${rule.metadata.hostname}/`, rule.metadata.value).filterText;
  if (expected !== rule.filterText) throw new Error("ClearBlock sync data contains an invalid rule.");
  const invalid = EWE.filters.validate(rule.filterText);
  if (invalid) throw new Error(invalid.reason);
}

async function applyCloudSnapshot(snapshot: SyncSnapshot): Promise<void> {
  snapshot.rules.forEach(validateManagedRule);
  const localRules = await getManagedRules();
  const cloudByText = new Map(snapshot.rules.map(rule => [rule.filterText, rule]));
  const localByText = new Map(localRules.map(rule => [rule.filterText, rule]));
  const removals = localRules.filter(rule => {
    const cloud = cloudByText.get(rule.filterText);
    return !cloud || !sameManagedRule(rule, cloud);
  });
  if (removals.length) await EWE.filters.remove(removals.map(rule => rule.filterText));

  for (const rule of snapshot.rules) {
    const local = localByText.get(rule.filterText);
    if (!local || !sameManagedRule(local, rule)) {
      await EWE.filters.add(rule.filterText, {clearBlock: rule.metadata});
    }
  }
}

async function initializeUserRuleSync(): Promise<void> {
  const stored = await chrome.storage.local.get(USER_SYNC_ENABLED_KEY);
  userSyncEnabled = stored[USER_SYNC_ENABLED_KEY] === true;
  if (!userSyncEnabled) return;
  try {
    const cloud = await readCloudSnapshot();
    if (cloud) await applyCloudSnapshot(cloud);
    else await writeCloudSnapshot();
    userSyncError = null;
  } catch (error) {
    userSyncError = error instanceof Error ? error.message : String(error);
  }
}

const userRuleSyncReady = engineReady.then(initializeUserRuleSync);

async function publishManagedRules(): Promise<void> {
  if (!userSyncEnabled) return;
  try {
    await writeCloudSnapshot();
    userSyncError = null;
  } catch (error) {
    userSyncError = error instanceof Error ? error.message : String(error);
    console.error("ClearBlock failed to synchronize user rules", error);
  }
}

async function setUserSyncEnabled(enabled: boolean): Promise<void> {
  if (userSyncEnabled === enabled) return;
  userSyncEnabled = enabled;
  await chrome.storage.local.set({[USER_SYNC_ENABLED_KEY]: enabled});
  userSyncError = null;
  if (!enabled) return;

  try {
    const localRules = await getManagedRules();
    const cloud = await readCloudSnapshot();
    const merged = cloud ? mergeSyncedRules(cloud.rules, localRules) : localRules;
    if (cloud) await applyCloudSnapshot({...cloud, rules: merged});
    await writeCloudSnapshot(merged);
  } catch (error) {
    userSyncError = error instanceof Error ? error.message : String(error);
  }
}

chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName !== "sync" || !userSyncEnabled) return;
  if (!Object.keys(changes).some(key => key === SYNC_MANIFEST_KEY || key.startsWith(SYNC_CHUNK_PREFIX))) return;
  if (syncChangeTimer !== undefined) clearTimeout(syncChangeTimer);
  syncChangeTimer = setTimeout(() => {
    syncChangeTimer = undefined;
    void userRuleSyncReady.then(async () => {
      try {
        const cloud = await readCloudSnapshot();
        if (cloud) await applyCloudSnapshot(cloud);
        userSyncError = null;
      } catch (error) {
        userSyncError = error instanceof Error ? error.message : String(error);
        console.error("ClearBlock failed to apply synchronized user rules", error);
      }
    });
  }, 100) as unknown as number;
});

chrome.webNavigation.onCommitted.addListener(details => {
  if (details.frameId !== 0) return;
  void loadCounters().then(() => {
    counters.tabs[String(details.tabId)] = 0;
    scheduleCounterFlush();
  });
});

chrome.tabs.onRemoved.addListener(tabId => {
  void loadCounters().then(() => {
    delete counters.tabs[String(tabId)];
    scheduleCounterFlush();
  });
});

chrome.runtime.onSuspend.addListener(() => void flushCounters());

async function getActiveTab(): Promise<chrome.tabs.Tab | undefined> {
  const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
  return tab;
}

function isSupportedTab(tab: chrome.tabs.Tab | undefined): tab is chrome.tabs.Tab & {id: number; url: string} {
  if (tab?.id === undefined || !tab.url) return false;
  try {
    canonicalPageUrl(tab.url);
    return true;
  } catch {
    return false;
  }
}

async function getPopupState(): Promise<PopupState> {
  await Promise.all([engineReady, loadCounters()]);
  const tab = await getActiveTab();
  if (!isSupportedTab(tab)) {
    return {
      supported: false,
      siteBlockingEnabled: false,
      pageBlockingEnabled: false,
      pageToggleDisabled: true,
      pageCount: 0,
      totalCount: counters.total
    };
  }

  const url = canonicalPageUrl(tab.url);
  const {allowlist} = classifyUserFilters(await EWE.filters.getUserFilters());
  const siteAllowed = allowlist.some(entry =>
    entry.scope === "site" && (url.hostname === entry.hostname || url.hostname.endsWith(`.${entry.hostname}`))
  );
  const pageAllowed = allowlist.some(entry => entry.scope === "page" && entry.value === url.href);

  return {
    supported: true,
    tabId: tab.id,
    url: url.href,
    hostname: url.hostname,
    pageLabel: `${url.pathname}${url.search}`,
    siteBlockingEnabled: !siteAllowed,
    pageBlockingEnabled: !siteAllowed && !pageAllowed,
    pageToggleDisabled: siteAllowed,
    pageCount: counters.tabs[String(tab.id)] ?? 0,
    totalCount: counters.total
  };
}

async function setBlocking(scope: "site" | "page", request: {
  tabId: number;
  url: string;
  enabled: boolean;
}): Promise<void> {
  const url = canonicalPageUrl(request.url);
  const value = scope === "site" ? url.hostname : url.href;
  const {allowlist} = classifyUserFilters(await EWE.filters.getUserFilters());
  const existing = allowlist.filter(entry => {
    if (entry.scope !== scope) return false;
    if (scope === "page") return entry.value === value;
    return url.hostname === entry.hostname || url.hostname.endsWith(`.${entry.hostname}`);
  });

  if (request.enabled) {
    if (existing.length) await EWE.filters.remove(existing.map(entry => entry.filterText));
  } else if (!existing.length) {
    const rule = createAllowlistRule(scope, value);
    const invalid = EWE.filters.validate(rule.filterText);
    if (invalid) throw new Error(invalid.reason);
    await EWE.filters.add(rule.filterText, rule.metadata);
  }
  await publishManagedRules();
  await chrome.tabs.reload(request.tabId);
}

async function getOptionsState(): Promise<OptionsState> {
  await engineReady;
  const filters = classifyUserFilters(await EWE.filters.getUserFilters());
  const subscriptions = await (EWE.subscriptions as unknown as SubscriptionApi).getSubscriptions();
  return {
    ...filters,
    userSync: {enabled: userSyncEnabled, error: userSyncError},
    subscriptions: subscriptions.map((subscription: Eyeo.Subscription): SubscriptionStatus => ({
      id: subscription.id ?? subscription.url,
      title: subscription.title,
      url: subscription.url,
      downloading: Boolean(subscription.downloading),
      downloadStatus: subscription.downloadStatus ?? null,
      lastSuccess: subscription.lastSuccess ?? null
    }))
  };
}

async function handleRequest(request: RuntimeRequest): Promise<unknown> {
  await userRuleSyncReady;
  switch (request.type) {
    case "getPopupState":
      return getPopupState();
    case "setSiteBlocking":
      return setBlocking("site", request);
    case "setPageBlocking":
      return setBlocking("page", request);
    case "startElementPicker":
      await chrome.scripting.executeScript({target: {tabId: request.tabId}, files: ["picker.js"]});
      return undefined;
    case "addElementRule": {
      const rule = createElementRule(request.url, request.selector);
      const invalid = EWE.filters.validate(rule.filterText);
      if (invalid) throw new Error(invalid.reason);
      await EWE.filters.add(rule.filterText, rule.metadata);
      await publishManagedRules();
      return undefined;
    }
    case "getOptionsState":
      return getOptionsState();
    case "addAllowlist": {
      const rule = createAllowlistRule(request.scope, request.value);
      const invalid = EWE.filters.validate(rule.filterText);
      if (invalid) throw new Error(invalid.reason);
      const {allowlist} = classifyUserFilters(await EWE.filters.getUserFilters());
      if (!allowlist.some(entry => entry.filterText === rule.filterText)) {
        await EWE.filters.add(rule.filterText, rule.metadata);
        await publishManagedRules();
      }
      return undefined;
    }
    case "removeFilter":
      await EWE.filters.remove(request.filterText);
      await publishManagedRules();
      return undefined;
    case "clearAllowlist": {
      const {allowlist} = classifyUserFilters(await EWE.filters.getUserFilters());
      if (allowlist.length) await EWE.filters.remove(allowlist.map(entry => entry.filterText));
      await publishManagedRules();
      return undefined;
    }
    case "setUserSyncEnabled":
      await setUserSyncEnabled(request.enabled);
      return undefined;
    case "syncSubscriptions":
      await (EWE.subscriptions as unknown as SubscriptionApi).sync();
      return undefined;
  }
}

chrome.runtime.onMessage.addListener((request: RuntimeRequest, _sender, sendResponse) => {
  // eyeo owns this namespace and must supply its own content-filter responses.
  if (request?.type?.startsWith("ewe:")) return false;
  void handleRequest(request)
    .then(data => sendResponse({ok: true, data} satisfies RuntimeResponse))
    .catch(error => sendResponse({
      ok: false,
      error: error instanceof Error ? error.message : String(error)
    } satisfies RuntimeResponse));
  return true;
});

void engineReady.catch((error: unknown) => console.error("ClearBlock failed to start", error));
