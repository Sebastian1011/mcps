export type AllowlistScope = "site" | "page";

export interface ClearBlockMetadata {
  kind: "allowlist" | "element";
  scope?: AllowlistScope;
  value: string;
  hostname: string;
  createdAt: number;
}

export interface AllowlistEntry {
  filterText: string;
  scope: AllowlistScope;
  value: string;
  hostname: string;
  createdAt: number;
}

export interface ElementRule {
  filterText: string;
  hostname: string;
  selector: string;
  createdAt: number;
}

export interface SubscriptionStatus {
  id: string;
  title: string;
  url: string;
  downloading: boolean;
  downloadStatus: string | null;
  lastSuccess: number | null;
}

export interface PopupState {
  supported: boolean;
  tabId?: number;
  url?: string;
  hostname?: string;
  pageLabel?: string;
  siteBlockingEnabled: boolean;
  pageBlockingEnabled: boolean;
  pageToggleDisabled: boolean;
  pageCount: number;
  totalCount: number;
}

export interface OptionsState {
  allowlist: AllowlistEntry[];
  elementRules: ElementRule[];
  subscriptions: SubscriptionStatus[];
}

export type RuntimeRequest =
  | {type: "getPopupState"}
  | {type: "setSiteBlocking"; tabId: number; url: string; enabled: boolean}
  | {type: "setPageBlocking"; tabId: number; url: string; enabled: boolean}
  | {type: "startElementPicker"; tabId: number}
  | {type: "addElementRule"; url: string; selector: string}
  | {type: "getOptionsState"}
  | {type: "addAllowlist"; scope: AllowlistScope; value: string}
  | {type: "removeFilter"; filterText: string}
  | {type: "clearAllowlist"}
  | {type: "syncSubscriptions"};

export interface RuntimeResponse<T = unknown> {
  ok: boolean;
  data?: T;
  error?: string;
}
