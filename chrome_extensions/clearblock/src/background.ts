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
import type {
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
let counters: CounterState = {total: 0, tabs: {}};
let countersLoaded: Promise<void> | undefined;
let counterFlushTimer: number | undefined;

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
  await chrome.tabs.reload(request.tabId);
}

async function getOptionsState(): Promise<OptionsState> {
  await engineReady;
  const filters = classifyUserFilters(await EWE.filters.getUserFilters());
  const subscriptions = await (EWE.subscriptions as unknown as SubscriptionApi).getSubscriptions();
  return {
    ...filters,
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
  await engineReady;
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
      }
      return undefined;
    }
    case "removeFilter":
      await EWE.filters.remove(request.filterText);
      return undefined;
    case "clearAllowlist": {
      const {allowlist} = classifyUserFilters(await EWE.filters.getUserFilters());
      if (allowlist.length) await EWE.filters.remove(allowlist.map(entry => entry.filterText));
      return undefined;
    }
    case "syncSubscriptions":
      await (EWE.subscriptions as unknown as SubscriptionApi).sync();
      return undefined;
  }
}

chrome.runtime.onMessage.addListener((request: RuntimeRequest, _sender, sendResponse) => {
  void handleRequest(request)
    .then(data => sendResponse({ok: true, data} satisfies RuntimeResponse))
    .catch(error => sendResponse({
      ok: false,
      error: error instanceof Error ? error.message : String(error)
    } satisfies RuntimeResponse));
  return true;
});

void engineReady.catch((error: unknown) => console.error("ClearBlock failed to start", error));
