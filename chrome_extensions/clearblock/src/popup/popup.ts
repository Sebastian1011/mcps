import {formatNumber, localize, send} from "../ui";
import type {PopupState} from "../shared/types";

localize();

const supported = document.querySelector<HTMLElement>("#supported-content")!;
const unsupported = document.querySelector<HTMLElement>("#unsupported")!;
const hostname = document.querySelector<HTMLElement>("#hostname")!;
const pageLabel = document.querySelector<HTMLElement>("#page-label")!;
const pageCount = document.querySelector<HTMLElement>("#page-count")!;
const totalCount = document.querySelector<HTMLElement>("#total-count")!;
const error = document.querySelector<HTMLElement>("#error")!;
const siteToggle = document.querySelector<HTMLInputElement>("#site-toggle")!;
const pageToggle = document.querySelector<HTMLInputElement>("#page-toggle")!;
const blockElement = document.querySelector<HTMLButtonElement>("#block-element")!;
let state: PopupState;

async function load(): Promise<void> {
  try {
    state = await send<PopupState>({type: "getPopupState"});
    supported.hidden = !state.supported;
    unsupported.hidden = state.supported;
    if (!state.supported) return;
    hostname.textContent = state.hostname ?? "";
    pageLabel.textContent = state.pageLabel || "/";
    siteToggle.checked = state.siteBlockingEnabled;
    pageToggle.checked = state.pageBlockingEnabled;
    pageToggle.disabled = state.pageToggleDisabled;
    pageCount.textContent = formatNumber(state.pageCount);
    totalCount.textContent = formatNumber(state.totalCount);
  } catch (caught) {
    error.textContent = caught instanceof Error ? caught.message : String(caught);
  }
}

async function setToggle(scope: "site" | "page", enabled: boolean): Promise<void> {
  if (!state.tabId || !state.url) return;
  siteToggle.disabled = true;
  pageToggle.disabled = true;
  try {
    await send({
      type: scope === "site" ? "setSiteBlocking" : "setPageBlocking",
      tabId: state.tabId,
      url: state.url,
      enabled
    });
    window.close();
  } catch (caught) {
    error.textContent = caught instanceof Error ? caught.message : String(caught);
    await load();
  }
}

siteToggle.addEventListener("change", () => void setToggle("site", siteToggle.checked));
pageToggle.addEventListener("change", () => void setToggle("page", pageToggle.checked));
blockElement.addEventListener("click", async () => {
  if (!state.tabId) return;
  try {
    await send({type: "startElementPicker", tabId: state.tabId});
    window.close();
  } catch (caught) {
    error.textContent = caught instanceof Error ? caught.message : String(caught);
  }
});
document.querySelector("#settings")!.addEventListener("click", () => void chrome.runtime.openOptionsPage());

void load();
