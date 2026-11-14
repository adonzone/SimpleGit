#!/usr/bin/env node
"use strict";

const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const vendorExe = path.join(
  __dirname,
  "..",
  "vendor",
  process.platform === "win32" ? "sgit.exe" : "sgit"
);
const repoRoot = path.resolve(__dirname, "..", "..", "..");
const hasLocalPkg = fs.existsSync(path.join(repoRoot, "simplegit", "__main__.py"));
const usePython = process.env.SGIT_USE_PYTHON === "1" || !fs.existsSync(vendorExe);

if (!usePython && fs.existsSync(vendorExe)) {
  const res = spawnSync(vendorExe, process.argv.slice(2), { stdio: "inherit" });
  process.exit(res.status === null ? 1 : res.status);
}

const pythonCandidates =
  process.platform === "win32" ? [["py", ["-3"]], ["python", []]] : [["python3", []], ["python", []]];

const env = { ...process.env };
if (hasLocalPkg) {
  env.PYTHONPATH = env.PYTHONPATH ? `${repoRoot}${path.delimiter}${env.PYTHONPATH}` : repoRoot;
}

for (const [cmd, prefixArgs] of pythonCandidates) {
  const res = spawnSync(cmd, [...prefixArgs, "-m", "simplegit", ...process.argv.slice(2)], {
    stdio: "inherit",
    env,
  });
  if (!res.error) {
    process.exit(res.status === null ? 1 : res.status);
  }
}

console.error(
  "sgit-cli error: neither the prebuilt sgit binary nor Python 3.10+ was found.\n" +
    "Reinstall sgit-cli or install Python 3.10+ and Git."
);
process.exit(1);
