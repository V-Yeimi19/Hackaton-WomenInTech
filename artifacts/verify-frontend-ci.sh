#!/usr/bin/env bash
set -euo pipefail
mkdir -p /work/frontend
tar -C /source --exclude=node_modules --exclude='.next*' --exclude='.env*' --exclude=playwright-report --exclude=test-results --exclude=tsconfig.tsbuildinfo -cf - . | tar -C /work/frontend -xf -
cd /work/frontend
node --version
npm --version
npm ci
npm run api:types
node -e 'const fs=require("fs");const path="src/lib/api/schema.d.ts";const normalize=s=>s.replace(/\r\n/g,"\n");if(normalize(fs.readFileSync(path,"utf8"))!==normalize(fs.readFileSync("/source/"+path,"utf8")))throw new Error("Generated API types differ from working tree");console.log("API contract types match");'
npm run lint
npm run typecheck
npm test
npm run build
printf '\nFRONTEND_CI_OK\n'
