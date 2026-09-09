import {createHash} from "node:crypto";
import {execFile} from "node:child_process";
import {cp, mkdir, readFile, rm, writeFile} from "node:fs/promises";
import path from "node:path";
import {promisify} from "node:util";
import {fileURLToPath} from "node:url";

const execFileAsync = promisify(execFile);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const work = path.join(root, "rules-work");
const output = path.join(root, "rules");
const recommendationsPath = path.join(work, "recommendations.json");
const indexUrl = "https://easylist-downloads.adblockplus.org/v3/index.json";
const selectedIds = new Set([
  "8C13E995-8F06-4927-BEA7-6C845FB7EEBF", // EasyList
  "D72B6F06-52B2-4FED-96A2-1BF59CDD7AEC", // EasyPrivacy
  "1D7F590C-B752-4BA0-9473-6A26DE1326B1", // EasyList China
  "D4028CDD-3D39-4624-ACC7-8140F4EC3238"  // ABP anti-circumvention (player snippets)
]);

async function run(binary, args) {
  const executable = path.join(root, "node_modules", ".bin", binary);
  const {stdout, stderr} = await execFileAsync(executable, args, {
    cwd: root,
    maxBuffer: 16 * 1024 * 1024
  });
  if (stdout) process.stdout.write(stdout);
  if (stderr) process.stderr.write(stderr);
}

async function sha256(file) {
  return createHash("sha256").update(await readFile(file)).digest("hex");
}

const response = await fetch(indexUrl);
if (!response.ok) {
  throw new Error(`Unable to fetch subscription index: ${response.status}`);
}

const index = await response.json();
const recommendations = index.filter(item => selectedIds.has(item.id));
if (recommendations.length !== selectedIds.size) {
  throw new Error("The subscription index did not contain all required lists.");
}

await rm(work, {recursive: true, force: true});
await mkdir(work, {recursive: true});
await writeFile(recommendationsPath, JSON.stringify(recommendations, null, 2));

await run("subs-fetch", [
  "--input", recommendationsPath,
  "--output", path.join(work, "subscriptions")
]);
await run("subs-convert", [
  "--input", path.join(work, "subscriptions"),
  "--output", path.join(work, "rulesets"),
  "--recommended-subscriptions", recommendationsPath,
  "--pretty-print"
]);
await run("subs-generate", [
  "--input", path.join(work, "rulesets"),
  "--output", path.join(work, "rulesets.json"),
  "--prefix", "rulesets/",
  "--default-enabled", ...selectedIds
]);

const files = [];
for (const item of recommendations) {
  const subscription = path.join(work, "subscriptions", item.id);
  const ruleset = path.join(work, "rulesets", item.id);
  files.push({
    id: item.id,
    subscriptionSha256: await sha256(subscription),
    rulesetSha256: await sha256(ruleset)
  });
}

await writeFile(path.join(work, "metadata.json"), JSON.stringify({
  generatedAt: new Date().toISOString(),
  source: indexUrl,
  files
}, null, 2));

await rm(output, {recursive: true, force: true});
await mkdir(output, {recursive: true});
await cp(path.join(work, "subscriptions"), path.join(output, "subscriptions"), {recursive: true});
await cp(path.join(work, "rulesets"), path.join(output, "rulesets"), {recursive: true});
await cp(recommendationsPath, path.join(output, "recommendations.json"));
await cp(path.join(work, "rulesets.json"), path.join(output, "rulesets.json"));
await cp(path.join(work, "metadata.json"), path.join(output, "metadata.json"));

console.log(`Updated ${recommendations.length} ClearBlock filter lists.`);
