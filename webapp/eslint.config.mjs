import { defineConfig, globalIgnores } from "eslint/config";
import next from "eslint-config-next";
import prettier from "eslint-config-prettier";
import jsxA11y from "eslint-plugin-jsx-a11y";

// eslint-plugin-jsx-a11y's recommended rules, reported as warnings while the
// existing hits are worked down. eslint-config-next already registers the
// plugin, so only the rule levels are set here (rule options are kept).
const a11yWarnings = Object.fromEntries(
    Object.entries(jsxA11y.flatConfigs.recommended.rules).map(([rule, setting]) => [rule, Array.isArray(setting) ? ["warn", ...setting.slice(1)] : "warn"]),
);
// label-has-associated-control calls minimatch's default export, which the
// minimatch 10 pinned in package.json "resolutions" no longer has: the rule
// crashes the whole lint run. Off until the plugin supports minimatch 10.
a11yWarnings["jsx-a11y/label-has-associated-control"] = "off";

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
            ...a11yWarnings,
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
