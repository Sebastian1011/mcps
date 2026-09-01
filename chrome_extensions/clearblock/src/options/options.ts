import {localize, send} from "../ui";
import type {AllowlistEntry, ElementRule, OptionsState, SubscriptionStatus} from "../shared/types";

localize();

const allowlistNode = document.querySelector<HTMLElement>("#allowlist")!;
const elementsNode = document.querySelector<HTMLElement>("#elements")!;
const subscriptionsNode = document.querySelector<HTMLElement>("#subscriptions")!;
const allowlistEmpty = document.querySelector<HTMLElement>("#allowlist-empty")!;
const elementsEmpty = document.querySelector<HTMLElement>("#elements-empty")!;
const status = document.querySelector<HTMLElement>("#status")!;
const search = document.querySelector<HTMLInputElement>("#search")!;
const scope = document.querySelector<HTMLSelectElement>("#scope")!;
const value = document.querySelector<HTMLInputElement>("#value")!;
const updateButton = document.querySelector<HTMLButtonElement>("#update-now")!;
let state: OptionsState = {allowlist: [], elementRules: [], subscriptions: []};

function formatDate(timestamp: number | null): string {
  if (!timestamp) return chrome.i18n.getMessage("neverUpdated");
  return new Intl.DateTimeFormat(chrome.i18n.getUILanguage(), {
    dateStyle: "medium", timeStyle: "short"
  }).format(new Date(timestamp));
}

function removeButton(filterText: string): HTMLButtonElement {
  const button = document.createElement("button");
  button.className = "remove";
  button.type = "button";
  button.textContent = chrome.i18n.getMessage("remove");
  button.addEventListener("click", async () => {
    await perform(async () => send({type: "removeFilter", filterText}), "removed");
  });
  return button;
}

function allowlistRow(entry: AllowlistEntry): HTMLElement {
  const row = document.createElement("div");
  row.className = "row";
  const main = document.createElement("div");
  main.className = "row-main";
  const title = document.createElement("strong");
  title.textContent = entry.value;
  const detail = document.createElement("span");
  detail.textContent = entry.scope === "site"
    ? chrome.i18n.getMessage("websiteIncludesSubdomains")
    : chrome.i18n.getMessage("exactPage");
  main.append(title, detail);
  row.append(main, removeButton(entry.filterText));
  return row;
}

function elementRow(entry: ElementRule): HTMLElement {
  const row = document.createElement("div");
  row.className = "row";
  const main = document.createElement("div");
  main.className = "row-main";
  const title = document.createElement("strong");
  title.textContent = entry.hostname;
  const detail = document.createElement("span");
  detail.className = "code";
  detail.textContent = entry.selector;
  main.append(title, detail);
  row.append(main, removeButton(entry.filterText));
  return row;
}

function subscriptionRow(subscription: SubscriptionStatus): HTMLElement {
  const row = document.createElement("div");
  row.className = "row";
  const main = document.createElement("div");
  main.className = "row-main";
  const title = document.createElement("strong");
  title.textContent = subscription.title;
  const detail = document.createElement("span");
  const stateLabel = subscription.downloading
    ? chrome.i18n.getMessage("updating")
    : subscription.downloadStatus && subscription.downloadStatus !== "synchronize_ok"
      ? chrome.i18n.getMessage("updateFailed")
      : chrome.i18n.getMessage("lastUpdated", [formatDate(subscription.lastSuccess)]);
  detail.textContent = stateLabel;
  if (subscription.downloadStatus && subscription.downloadStatus !== "synchronize_ok") {
    detail.className = "failure";
    detail.title = subscription.downloadStatus;
  }
  main.append(title, detail);
  row.append(main);
  return row;
}

function render(): void {
  const query = search.value.trim().toLocaleLowerCase();
  const filtered = state.allowlist.filter(entry =>
    !query || entry.value.toLocaleLowerCase().includes(query)
  );
  allowlistNode.replaceChildren(...filtered.map(allowlistRow));
  allowlistEmpty.hidden = filtered.length > 0;
  elementsNode.replaceChildren(...state.elementRules.map(elementRow));
  elementsEmpty.hidden = state.elementRules.length > 0;
  subscriptionsNode.replaceChildren(...state.subscriptions.map(subscriptionRow));
}

async function load(): Promise<void> {
  state = await send<OptionsState>({type: "getOptionsState"});
  render();
}

async function perform(action: () => Promise<unknown>, successKey: string): Promise<void> {
  status.classList.remove("failure");
  try {
    await action();
    status.textContent = chrome.i18n.getMessage(successKey);
    await load();
  } catch (caught) {
    status.classList.add("failure");
    status.textContent = caught instanceof Error ? caught.message : String(caught);
  }
}

document.querySelector<HTMLFormElement>("#add-form")!.addEventListener("submit", event => {
  event.preventDefault();
  void perform(async () => {
    await send({type: "addAllowlist", scope: scope.value as "site" | "page", value: value.value});
    value.value = "";
  }, "added");
});
document.querySelector("#clear-all")!.addEventListener("click", () => {
  if (state.allowlist.length && confirm(chrome.i18n.getMessage("clearAllowlistConfirm"))) {
    void perform(() => send({type: "clearAllowlist"}), "allowlistCleared");
  }
});
search.addEventListener("input", render);
scope.addEventListener("change", () => {
  value.placeholder = chrome.i18n.getMessage(scope.value === "site" ? "sitePlaceholder" : "pagePlaceholder");
});
updateButton.addEventListener("click", () => {
  updateButton.disabled = true;
  void perform(() => send({type: "syncSubscriptions"}), "updateStarted")
    .finally(() => {
      updateButton.disabled = false;
      setTimeout(() => void load(), 2000);
    });
});

void load().catch(caught => {
  status.classList.add("failure");
  status.textContent = caught instanceof Error ? caught.message : String(caught);
});
