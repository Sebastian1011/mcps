import {build} from "esbuild";
import {cp, mkdir, readFile, rm, writeFile} from "node:fs/promises";
import path from "node:path";
import sharp from "sharp";
import {fileURLToPath} from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dist = path.join(root, "dist");
const rules = path.join(root, "rules");

async function copy(source, destination) {
  await mkdir(path.dirname(destination), {recursive: true});
  await cp(source, destination, {recursive: true});
}

await rm(dist, {recursive: true, force: true});
await mkdir(dist, {recursive: true});

const entries = [
  ["src/background.ts", "background.js"],
  ["src/picker.ts", "picker.js"],
  ["src/popup/popup.ts", "popup.js"],
  ["src/options/options.ts", "options.js"]
];

for (const [entry, outfile] of entries) {
  await build({
    entryPoints: [path.join(root, entry)],
    outfile: path.join(dist, outfile),
    bundle: true,
    format: "iife",
    platform: "browser",
    target: "chrome127",
    minify: true,
    legalComments: "none"
  });
}

await Promise.all([
  copy(path.join(root, "src/popup/index.html"), path.join(dist, "popup.html")),
  copy(path.join(root, "src/popup/popup.css"), path.join(dist, "popup.css")),
  copy(path.join(root, "src/options/index.html"), path.join(dist, "options.html")),
  copy(path.join(root, "src/options/options.css"), path.join(dist, "options.css")),
  copy(path.join(root, "_locales"), path.join(dist, "_locales")),
  copy(path.join(rules, "subscriptions"), path.join(dist, "subscriptions")),
  copy(path.join(rules, "rulesets"), path.join(dist, "rulesets")),
  copy(
    path.join(root, "node_modules/@eyeo/webext-ad-filtering-solution/dist/ewe-api.js"),
    path.join(dist, "vendor/ewe-api.js")
  ),
  copy(
    path.join(root, "node_modules/@eyeo/webext-ad-filtering-solution/dist/ewe-content.js"),
    path.join(dist, "vendor/ewe-content.js")
  ),
  copy(
    path.join(root, "node_modules/@eyeo/webext-ad-filtering-solution/dist/ewe-content-main.js"),
    path.join(dist, "vendor/ewe-content-main.js")
  )
]);

const iconSource = path.join(root, "src/icons/logo.svg");
await mkdir(path.join(dist, "icons"), {recursive: true});
for (const size of [16, 32, 48, 128]) {
  await sharp(iconSource).resize(size, size).png().toFile(path.join(dist, `icons/icon-${size}.png`));
}

const manifestVersion = JSON.parse(await readFile(path.join(root, "package.json"), "utf8")).version;
const dnr = JSON.parse(await readFile(path.join(rules, "rulesets.json"), "utf8"));
const manifest = {
  manifest_version: 3,
  name: "__MSG_extensionName__",
  short_name: "ClearBlock",
  description: "__MSG_extensionDescription__",
  version: manifestVersion,
  minimum_chrome_version: "127",
  default_locale: "en",
  action: {
    default_title: "ClearBlock",
    default_popup: "popup.html",
    default_icon: {
      16: "icons/icon-16.png",
      32: "icons/icon-32.png",
      48: "icons/icon-48.png"
    }
  },
  icons: {
    16: "icons/icon-16.png",
    32: "icons/icon-32.png",
    48: "icons/icon-48.png",
    128: "icons/icon-128.png"
  },
  background: {service_worker: "background.js"},
  options_ui: {page: "options.html", open_in_tab: true},
  permissions: [
    "declarativeNetRequest",
    "scripting",
    "storage",
    "tabs",
    "webNavigation",
    "webRequest",
    "unlimitedStorage"
  ],
  host_permissions: ["http://*/*", "https://*/*"],
  content_scripts: [
    {
      all_frames: true,
      js: ["vendor/ewe-content.js"],
      match_about_blank: true,
      matches: ["http://*/*", "https://*/*"],
      run_at: "document_start"
    },
    {
      all_frames: true,
      js: ["vendor/ewe-content-main.js"],
      match_about_blank: true,
      matches: ["http://*/*", "https://*/*"],
      run_at: "document_start",
      world: "MAIN"
    }
  ],
  declarative_net_request: dnr
};

await writeFile(path.join(dist, "manifest.json"), JSON.stringify(manifest, null, 2));
await copy(
  path.join(root, "node_modules/@eyeo/webext-ad-filtering-solution/COPYING"),
  path.join(dist, "COPYING")
);
console.log(`Built ClearBlock ${manifestVersion} in ${dist}`);
