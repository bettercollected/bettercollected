import { defineConfig, globalIgnores } from "eslint/config";
import next from "eslint-config-next";
import path from "node:path";
import { fileURLToPath } from "node:url";
import js from "@eslint/js";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const compat = new FlatCompat({
    baseDirectory: __dirname,
    recommendedConfig: js.configs.recommended,
    allConfig: js.configs.all
});

export default defineConfig([globalIgnores([
    "**/.github",
    "**/.next",
    "**/.next-dev",
    "**/.vercel",
    "**/.husky",
    "**/.vscode",
    "**/node_modules",
    "**/build",
    "**/public",
    "**/.eslintrc.json",
    "**/package.json",
    "**/package-lock.json",
    "**/tsconfig.json",
    "**/yarn.lock",
]), {
    extends: [...next, ...compat.extends("prettier")],

    rules: {
        "react-hooks/exhaustive-deps": "off",
    },
}]);