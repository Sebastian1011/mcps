import archiver from "archiver";
import {createWriteStream} from "node:fs";
import {mkdir, readFile} from "node:fs/promises";
import path from "node:path";
import {fileURLToPath} from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const version = JSON.parse(await readFile(path.join(root, "package.json"), "utf8")).version;
const artifacts = path.join(root, "artifacts");
await mkdir(artifacts, {recursive: true});
const destination = path.join(artifacts, `clearblock-${version}.zip`);

await new Promise((resolve, reject) => {
  const output = createWriteStream(destination);
  const archive = archiver("zip", {zlib: {level: 9}});
  output.on("close", resolve);
  output.on("error", reject);
  archive.on("error", reject);
  archive.pipe(output);
  archive.directory(path.join(root, "dist"), false);
  void archive.finalize();
});

console.log(`Packaged ${destination}`);
