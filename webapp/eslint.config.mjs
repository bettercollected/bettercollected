import { defineConfig, globalIgnores } from "eslint/config";
import next from "eslint-config-next";
import prettier from "eslint-config-prettier";
import jsxA11y from "eslint-plugin-jsx-a11y";
import { plugin as shadcn } from "@shadcn/lint";

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
// Its deprecated predecessor stands in, accepting either way of tying a label
// to its control (htmlFor + id, or nesting) instead of demanding both.
a11yWarnings["jsx-a11y/label-has-for"] = ["warn", { required: { some: ["nesting", "id"] } }];

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
    {
        // @shadcn/lint: Tailwind design-system rules. Registered but all OFF; turning rules on is a
        // separate decision. Counts per rule and a suggested order: docs/webapp-shadcn-lint-baseline.md.
        // Components and theme are discovered from components.json. To check code against one rule
        // without enabling it: yarn lint --rule 'shadcn/no-raw-colors: warn' <paths>
        files: ["src/**/*.{ts,tsx,js,jsx}"],
        plugins: { shadcn },
        rules: {
            "shadcn/no-restyle": "off",
            "shadcn/no-raw-colors": "off",
            "shadcn/no-arbitrary-values": "off",
            "shadcn/no-inline-styles": "off",
            "shadcn/no-unknown-classes": "off",
            "shadcn/require-static-classes": "off",
        },
    },
]);
