import {chromium, expect, test, type BrowserContext} from "@playwright/test";
import {createServer, type Server} from "node:http";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "../..");
const extensionPath = path.join(root, "dist");
let context: BrowserContext;
let extensionId: string;
let server: Server;
let fixtureUrl: string;

test.beforeAll(async () => {
  server = createServer((request, response) => {
    response.setHeader("content-type", request.url?.endsWith(".js") ? "text/javascript" : "text/html");
    if (request.url === "/assets/ads/banner.js") {
      response.end("window.adScriptLoaded = true;");
    } else if (request.url === "/app.js") {
      response.end("window.appScriptLoaded = true;");
    } else {
      response.end(`<!doctype html><title>ClearBlock fixture</title>
        <div class="sponsor-card">Sponsored</div>
        <script src="/app.js"></script><script src="/assets/ads/banner.js"></script>`);
    }
  });
  await new Promise<void>(resolve => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("Fixture server failed to bind.");
  fixtureUrl = `http://clearblock.test:${address.port}/article?case=1`;

  context = await chromium.launchPersistentContext("", {
    channel: "chromium",
    headless: true,
    args: [
      "--host-resolver-rules=MAP clearblock.test 127.0.0.1",
      `--disable-extensions-except=${extensionPath}`,
      `--load-extension=${extensionPath}`
    ]
  });
  let worker = context.serviceWorkers()[0];
  worker ??= await context.waitForEvent("serviceworker", {timeout: 30_000});
  extensionId = new URL(worker.url()).host;
});

test.afterAll(async () => {
  await context?.close();
  await new Promise<void>((resolve, reject) => server?.close(error => error ? reject(error) : resolve()));
});

test("blocks a matching EasyList request and honors a site allowlist", async () => {
  const fixture = await context.newPage();
  await fixture.goto(fixtureUrl);
  await expect.poll(() => fixture.evaluate(() => (window as typeof window & {appScriptLoaded?: boolean}).appScriptLoaded))
    .toBe(true);
  expect(await fixture.evaluate(() => (window as typeof window & {adScriptLoaded?: boolean}).adScriptLoaded))
    .toBeUndefined();

  const options = await context.newPage();
  await options.goto(`chrome-extension://${extensionId}/options.html`);
  const addResponse = await options.evaluate(() => chrome.runtime.sendMessage({
    type: "addAllowlist", scope: "site", value: "clearblock.test"
  }));
  expect(addResponse.ok).toBe(true);

  await fixture.reload();
  await expect.poll(() => fixture.evaluate(() => (window as typeof window & {adScriptLoaded?: boolean}).adScriptLoaded))
    .toBe(true);

  await fixture.bringToFront();
  const popupResponse = await options.evaluate(() => chrome.runtime.sendMessage({type: "getPopupState"}));
  expect(popupResponse.ok).toBe(true);
  expect(popupResponse.data).toMatchObject({
    supported: true,
    hostname: "clearblock.test",
    siteBlockingEnabled: false,
    pageToggleDisabled: true
  });

  const optionsState = await options.evaluate(() => chrome.runtime.sendMessage({type: "getOptionsState"}));
  const filterText = optionsState.data.allowlist[0].filterText;
  const removeResponse = await options.evaluate(text => chrome.runtime.sendMessage({
    type: "removeFilter", filterText: text
  }), filterText);
  expect(removeResponse.ok).toBe(true);

  const pageResponse = await options.evaluate(url => chrome.runtime.sendMessage({
    type: "addAllowlist", scope: "page", value: url
  }), fixtureUrl);
  expect(pageResponse.ok).toBe(true);
  await fixture.reload();
  await expect.poll(() => fixture.evaluate(() => (window as typeof window & {adScriptLoaded?: boolean}).adScriptLoaded))
    .toBe(true);

  await fixture.goto(new URL("/another-page", fixtureUrl).href);
  expect(await fixture.evaluate(() => (window as typeof window & {adScriptLoaded?: boolean}).adScriptLoaded))
    .toBeUndefined();

  const finalState = await options.evaluate(() => chrome.runtime.sendMessage({type: "getOptionsState"}));
  const pageFilter = finalState.data.allowlist[0].filterText;
  await options.evaluate(text => chrome.runtime.sendMessage({type: "removeFilter", filterText: text}), pageFilter);
});

test("publishes and applies synchronized user rules", async () => {
  const options = await context.newPage();
  await options.goto(`chrome-extension://${extensionId}/options.html`);

  const initial = await options.evaluate(() => chrome.runtime.sendMessage({type: "getOptionsState"}));
  expect(initial.data.userSync).toEqual({enabled: false, error: null});

  await expect(options.locator("#user-sync")).not.toBeChecked();
  await options.locator("#user-sync").check();
  await expect.poll(async () => {
    const response = await options.evaluate(() => chrome.runtime.sendMessage({type: "getOptionsState"}));
    return response.data.userSync.enabled;
  }).toBe(true);
  const added = await options.evaluate(() => chrome.runtime.sendMessage({
    type: "addAllowlist", scope: "site", value: "sync-local.test"
  }));
  expect(added.ok).toBe(true);

  await expect.poll(() => options.evaluate(async () => {
    const stored = await chrome.storage.sync.get(null);
    const manifest = stored.clearBlockUserRulesManifest as {chunkCount?: number} | undefined;
    return manifest?.chunkCount
      && Array.from({length: manifest.chunkCount}, (_, index) => stored[`clearBlockUserRulesChunk:${index}`])
        .every(chunk => typeof chunk === "string");
  })).toBe(true);

  await options.evaluate(async () => {
    const updatedAt = Date.now() + 1_000;
    const payload = {
      version: 1,
      updatedAt,
      rules: [{
        filterText: "@@||sync-remote.test^$document",
        metadata: {
          kind: "allowlist",
          scope: "site",
          value: "sync-remote.test",
          hostname: "sync-remote.test",
          createdAt: updatedAt
        }
      }]
    };
    const bytes = new TextEncoder().encode(JSON.stringify(payload));
    let binary = "";
    for (const byte of bytes) binary += String.fromCharCode(byte);
    await chrome.storage.sync.set({
      clearBlockUserRulesManifest: {version: 1, chunkCount: 1, updatedAt},
      "clearBlockUserRulesChunk:0": btoa(binary)
    });
  });

  await expect.poll(async () => {
    const response = await options.evaluate(() => chrome.runtime.sendMessage({type: "getOptionsState"}));
    return response.data.allowlist.map((entry: {value: string}) => entry.value);
  }).toEqual(["sync-remote.test"]);

  const visibleState = await options.evaluate(() => chrome.runtime.sendMessage({type: "getOptionsState"}));
  expect(visibleState.data.userSync).toEqual({enabled: true, error: null});
  await options.evaluate(() => chrome.runtime.sendMessage({type: "setUserSyncEnabled", enabled: false}));
  await options.evaluate(() => chrome.runtime.sendMessage({type: "clearAllowlist"}));
  await options.evaluate(() => chrome.storage.sync.clear());
});

test("loads the popup and options pages from the installed extension", async () => {
  const page = await context.newPage();
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));

  await page.goto(`chrome-extension://${extensionId}/popup.html`);
  await expect(page.locator(".brand")).toContainText("ClearBlock");
  await expect(page.locator("#unsupported")).toBeVisible();
  if (process.env.CLEARBLOCK_SCREENSHOTS) {
    await page.setViewportSize({width: 380, height: 560});
    await page.evaluate(() => {
      document.querySelector<HTMLElement>("#unsupported")!.hidden = true;
      document.querySelector<HTMLElement>("#supported-content")!.hidden = false;
      document.querySelector<HTMLElement>("#hostname")!.textContent = "example.com";
      document.querySelector<HTMLElement>("#page-label")!.textContent = "/articles/clearblock";
      document.querySelector<HTMLInputElement>("#site-toggle")!.checked = true;
      document.querySelector<HTMLInputElement>("#page-toggle")!.checked = true;
      document.querySelector<HTMLElement>("#page-count")!.textContent = "25";
      document.querySelector<HTMLElement>("#total-count")!.textContent = "1,327";
    });
    await page.screenshot({path: "/tmp/clearblock-popup.png", fullPage: true});
  }

  await page.goto(`chrome-extension://${extensionId}/options.html`);
  await expect(page.locator("h1")).toHaveText("Allowlist");
  await expect(page.locator("#user-sync")).not.toBeChecked();
  await expect(page.locator("#subscriptions .row")).toHaveCount(4, {timeout: 30_000});
  await expect(page.locator("#subscriptions")).not.toContainText("1970");
  if (process.env.CLEARBLOCK_SCREENSHOTS) {
    await page.setViewportSize({width: 1180, height: 900});
    await page.screenshot({path: "/tmp/clearblock-options.png", fullPage: true});
  }
  expect(errors).toEqual([]);
});

test("YouTube filters preroll data before playback without a Skip button", async () => {
  const options = await context.newPage();
  await options.goto(`chrome-extension://${extensionId}/options.html`);
  await options.evaluate(() => chrome.runtime.sendMessage({type: "getOptionsState"}));
  const page = await context.newPage();
  const requests: string[] = [];
  const pageErrors: string[] = [];
  page.on("pageerror", error => pageErrors.push(error.message));
  await page.route("https://www.youtube.com/**", route => {
    const url = new URL(route.request().url());
    if (url.pathname.startsWith("/fixture-")) {
      requests.push(url.pathname);
      return route.fulfill({body: "ok"});
    }
    return route.fulfill({contentType: "text/html", body: `<!doctype html>
      <title>YouTube player-data fixture</title>
      <script>
        function setPlayerResponse() {
          const response = () => ({
            adSlots: [{adSlotRenderer: {}}], adPlacements: [{adPlacementRenderer: {}}],
            playerAds: [{playerLegacyDesktopWatchAdsRenderer: {}}],
            videoDetails: {videoId: 'content-video'}, streamingData: {formats: [{url: '/fixture-content'}]}
          });
          window.ytInitialPlayerResponse = response();
          window.ytplayer = {config: {args: {raw_player_response: response()}}};
        }
        setPlayerResponse();
        window.initialAdFields = [ytInitialPlayerResponse.adSlots,
          ytInitialPlayerResponse.adPlacements, ytInitialPlayerResponse.playerAds,
          ytplayer.config.args.raw_player_response.adSlots,
          ytplayer.config.args.raw_player_response.adPlacements,
          ytplayer.config.args.raw_player_response.playerAds].map(value => value !== undefined);
        function playContent() {
          const data = window.ytInitialPlayerResponse;
          window.adFields = [data.adSlots, data.adPlacements, data.playerAds,
            ytplayer.config.args.raw_player_response.adSlots,
            ytplayer.config.args.raw_player_response.adPlacements,
            ytplayer.config.args.raw_player_response.playerAds].map(value => value !== undefined);
          window.selectedMedia = window.adFields.some(Boolean) ? '/fixture-commercial' : data.streamingData.formats[0].url;
          fetch(window.selectedMedia);
        }
        if (new URLSearchParams(location.search).has('autoplay')) playContent();
      </script>
      <button id="play" onclick="playContent()">Play content</button>`});
  });
  const url = "https://www.youtube.com/watch?v=clearblock-preroll";
  // Cold initialization and allowlist changes refresh eyeo's cache and reload
  // the document. Assert filtering at the first inline script of that document.
  const initialized = (allowed: boolean) => page.waitForFunction(allowed => {
    const fields = (window as typeof window & {initialAdFields?: boolean[]}).initialAdFields;
    return fields?.length === 6 && fields.every(value => value === allowed);
  }, allowed, {timeout: 5000});
  const play = async (expected: string) => {
    await page.locator("#play").click();
    expect(await page.evaluate(() => (window as typeof window & {selectedMedia: string}).selectedMedia)).toBe(expected);
    await expect.poll(() => requests.at(-1)).toBe(expected);
  };
  await page.goto(url);
  await initialized(false);
  await play("/fixture-content");
  expect(requests).not.toContain("/fixture-commercial");
  const beforeAutoplay = requests.length;
  await page.goto(`${url}&autoplay=1`);
  await expect.poll(() => requests.length).toBeGreaterThan(beforeAutoplay);
  expect(requests).not.toContain("/fixture-commercial");
  await page.evaluate(() => {
    history.pushState({}, "", "/watch?v=clearblock-next");
    (window as typeof window & {setPlayerResponse: () => void}).setPlayerResponse();
  });
  await play("/fixture-content");

  for (const scope of ["site", "page"] as const) {
    const added = await options.evaluate(({scope, url}) => chrome.runtime.sendMessage({
      type: "addAllowlist", scope, value: scope === "site" ? "youtube.com" : url
    }), {scope, url});
    expect(added.ok).toBe(true);
    await page.goto(url);
    await initialized(true);
    await play("/fixture-commercial");
    const state = await options.evaluate(() => chrome.runtime.sendMessage({type: "getOptionsState"}));
    const filterText = state.data.allowlist.find((entry: {scope: string}) => entry.scope === scope).filterText;
    await options.evaluate(filterText => chrome.runtime.sendMessage({type: "removeFilter", filterText}), filterText);
    await page.reload();
    await initialized(false);
    await play("/fixture-content");
  }
  expect(pageErrors).toEqual([]);
  await page.close();
  await options.close();
});
