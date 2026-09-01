import type {
  AllowlistEntry,
  AllowlistScope,
  ClearBlockMetadata,
  ElementRule
} from "./types";

const HTTP_PROTOCOLS = new Set(["http:", "https:"]);

export function canonicalPageUrl(input: string): URL {
  const url = new URL(input);
  if (!HTTP_PROTOCOLS.has(url.protocol)) {
    throw new Error("Only HTTP and HTTPS pages are supported.");
  }
  url.hash = "";
  return url;
}

export function hostnameFromInput(input: string): string {
  const trimmed = input.trim();
  const parsed = canonicalPageUrl(
    /^[a-z][a-z\d+.-]*:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`
  );
  if (!parsed.hostname || parsed.username || parsed.password) {
    throw new Error("Enter a valid hostname or URL.");
  }
  return parsed.hostname.toLowerCase();
}

export function siteExceptionFilter(hostname: string): string {
  if (!hostname || /[\s/^$|]/.test(hostname)) {
    throw new Error("The hostname cannot be represented as an allowlist rule.");
  }
  return `@@||${hostname}^$document`;
}

export function pageExceptionFilter(input: string): string {
  const value = canonicalPageUrl(input).href;
  const escaped = value.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&");
  return `@@/^${escaped}$/$document`;
}

export function elementHidingFilter(hostname: string, selector: string): string {
  const cleanSelector = selector.trim();
  if (!cleanSelector || cleanSelector.length > 1800 || /[\r\n]/.test(cleanSelector)) {
    throw new Error("The selected element produced an invalid selector.");
  }
  return `${hostname}##${cleanSelector}`;
}

export function createAllowlistRule(scope: AllowlistScope, input: string): {
  filterText: string;
  metadata: {clearBlock: ClearBlockMetadata};
} {
  const createdAt = Date.now();
  if (scope === "site") {
    const hostname = hostnameFromInput(input);
    return {
      filterText: siteExceptionFilter(hostname),
      metadata: {
        clearBlock: {kind: "allowlist", scope, value: hostname, hostname, createdAt}
      }
    };
  }

  const url = canonicalPageUrl(input);
  return {
    filterText: pageExceptionFilter(url.href),
    metadata: {
      clearBlock: {
        kind: "allowlist",
        scope,
        value: url.href,
        hostname: url.hostname.toLowerCase(),
        createdAt
      }
    }
  };
}

export function createElementRule(inputUrl: string, selector: string): {
  filterText: string;
  metadata: {clearBlock: ClearBlockMetadata};
} {
  const hostname = canonicalPageUrl(inputUrl).hostname.toLowerCase();
  return {
    filterText: elementHidingFilter(hostname, selector),
    metadata: {
      clearBlock: {kind: "element", value: selector, hostname, createdAt: Date.now()}
    }
  };
}

interface UserFilter {
  text: string;
  metadata?: {clearBlock?: ClearBlockMetadata};
}

export function classifyUserFilters(filters: UserFilter[]): {
  allowlist: AllowlistEntry[];
  elementRules: ElementRule[];
} {
  const allowlist: AllowlistEntry[] = [];
  const elementRules: ElementRule[] = [];

  for (const filter of filters) {
    const metadata = filter.metadata?.clearBlock;
    if (!metadata) continue;
    if (metadata.kind === "allowlist" && metadata.scope) {
      allowlist.push({
        filterText: filter.text,
        scope: metadata.scope,
        value: metadata.value,
        hostname: metadata.hostname,
        createdAt: metadata.createdAt
      });
    } else if (metadata.kind === "element") {
      elementRules.push({
        filterText: filter.text,
        hostname: metadata.hostname,
        selector: metadata.value,
        createdAt: metadata.createdAt
      });
    }
  }

  const newestFirst = <T extends {createdAt: number}>(a: T, b: T) => b.createdAt - a.createdAt;
  return {allowlist: allowlist.sort(newestFirst), elementRules: elementRules.sort(newestFirst)};
}
