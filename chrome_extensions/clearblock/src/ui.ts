import type {RuntimeRequest, RuntimeResponse} from "./shared/types";

export function localize(root: ParentNode = document): void {
  root.querySelectorAll<HTMLElement>("[data-i18n]").forEach(element => {
    const key = element.dataset.i18n;
    if (key) element.textContent = chrome.i18n.getMessage(key);
  });
  root.querySelectorAll<HTMLInputElement>("[data-i18n-placeholder]").forEach(element => {
    const key = element.dataset.i18nPlaceholder;
    if (key) element.placeholder = chrome.i18n.getMessage(key);
  });
  root.querySelectorAll<HTMLElement>("[data-i18n-aria]").forEach(element => {
    const key = element.dataset.i18nAria;
    if (key) element.setAttribute("aria-label", chrome.i18n.getMessage(key));
  });
}

export async function send<T>(request: RuntimeRequest): Promise<T> {
  const response = await chrome.runtime.sendMessage(request) as RuntimeResponse<T>;
  if (!response?.ok) throw new Error(response?.error || chrome.i18n.getMessage("unknownError"));
  return response.data as T;
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat(chrome.i18n.getUILanguage()).format(value);
}
