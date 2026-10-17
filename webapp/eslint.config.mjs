import { defineConfig, globalIgnores } from "eslint/config";
import next from "eslint-config-next";
import prettier from "eslint-config-prettier";

export default defineConfig([
    globalIgnores([
        "**/.github",
        "**/.next",
        "**/.next-dev",
        "**/.vercel",
        "**/.husky",
        "**/.vscode",
        "**/node_modules",
        "**/build",
        "**/public",
        "**/storybook-static",
        "**/coverage",
        "next-env.d.ts",
    ]),
    {
        extends: [...next, prettier],

        rules: {
            "react-hooks/exhaustive-deps": "off",
            // React Compiler diagnostics from eslint-plugin-react-hooks 7. The app does not use the
            // React Compiler, and existing code has many hits; keep them visible as warnings until
            // they are worked down. rules-of-hooks stays an error.
            "react-hooks/immutability": "warn",
            "react-hooks/set-state-in-effect": "warn",
            "react-hooks/refs": "warn",
            "react-hooks/globals": "warn",
            "react-hooks/purity": "warn",
            "react-hooks/preserve-manual-memoization": "warn",
        },
    },
]);
