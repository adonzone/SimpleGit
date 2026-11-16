"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const https = require("node:https");
const path = require("node:path");
const pkg = require("../package.json");

if (process.env.SGIT_SKIP_DOWNLOAD === "1") {
  process.exit(0);
}

const TARGETS = {
  "darwin-arm64": "sgit-darwin-arm64",
  "darwin-x64": "sgit-darwin-x64",
  "linux-x64": "sgit-linux-x64",
  "linux-arm64": "sgit-linux-arm64",
  "win32-x64": "sgit-win32-x64.exe",
};

const key = `${process.platform}-${process.arch}`;
const asset = TARGETS[key];
if (!asset) {
  console.warn(`[sgit-cli] No prebuilt binary for ${key}; will fall back to python3 -m simplegit.`);
  process.exit(0);
}

const repo = process.env.SGIT_RELEASE_REPO || "adonzone/SimpleGit";
const baseUrl = `https://github.com/${repo}/releases/download/v${pkg.version}`;
const vendorDir = path.join(__dirname, "..", "vendor");
const destFile = path.join(vendorDir, process.platform === "win32" ? "sgit.exe" : "sgit");

function fetchBuffer(url, redirects = 0) {
  return new Promise((resolve, reject) => {
    if (redirects > 5) return reject(new Error("Too many redirects"));
    https
      .get(url, (res) => {
        if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
          return resolve(fetchBuffer(res.headers.location, redirects + 1));
        }
        if (res.statusCode !== 200) {
          return reject(new Error(`HTTP ${res.statusCode} fetching ${url}`));
        }
        const chunks = [];
        res.on("data", (c) => chunks.push(c));
        res.on("end", () => resolve(Buffer.concat(chunks)));
      })
      .on("error", reject);
  });
}

(async () => {
  try {
    const [sumsBuf, binBuf] = await Promise.all([
      fetchBuffer(`${baseUrl}/SHA256SUMS.txt`),
      fetchBuffer(`${baseUrl}/${asset}`),
    ]);
    const expectedLine = sumsBuf
      .toString("utf8")
      .split(/\r?\n/)
      .find((ln) => ln.trim().endsWith(asset));
    if (!expectedLine) {
      throw new Error(`Checksum entry for ${asset} missing in SHA256SUMS.txt`);
    }
    const expectedSha = expectedLine.trim().split(/\s+/)[0].toLowerCase();
    const actualSha = crypto.createHash("sha256").update(binBuf).digest("hex").toLowerCase();
    if (expectedSha !== actualSha) {
      throw new Error(`SHA-256 mismatch for ${asset}: expected ${expectedSha}, got ${actualSha}`);
    }
    fs.mkdirSync(vendorDir, { recursive: true });
    fs.writeFileSync(destFile, binBuf);
    if (process.platform !== "win32") {
      fs.chmodSync(destFile, 0o755);
    }
  } catch (err) {
    console.warn(`[sgit-cli] Binary download skipped (${err.message}); Python fallback will be used.`);
  }
})();
