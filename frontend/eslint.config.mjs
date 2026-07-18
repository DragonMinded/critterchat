import globals from "globals";
import { defineConfig } from "eslint/config";
import js from "@eslint/js";
import ts from 'typescript-eslint';

export default defineConfig([
    {
        files: ["src/**/*.{js,ts}"],
        plugins: {
            js,
        },
        extends: [
            js.configs.recommended,
            ts.configs.recommendedTypeChecked,
        ],
        rules: {
            // Warns about unused parameteres as well, unless they're prefixed with _
            "@typescript-eslint/no-unused-vars": [
                "warn",
                {
                    "argsIgnorePattern": "^_",
                }
            ],
            // Duplicates the above.
            "no-unused-vars": "off",
            "no-undef": "warn",
            "no-prototype-builtins": "off",
            // We use these for hljs.
            "@typescript-eslint/no-require-imports": "off",
            // We should be allowed to ignore things.
            "@typescript-eslint/ban-ts-comment": "off",
            // We should also be able to use an any escape hatch.
            "@typescript-eslint/no-explicit-any": "off",
            "@typescript-eslint/no-unsafe-argument": "off",
            "@typescript-eslint/no-unsafe-assignment": "off",
            "@typescript-eslint/no-unsafe-call": "off",
            "@typescript-eslint/no-unsafe-member-access": "off",
            "@typescript-eslint/no-unsafe-return": "off",
        },
        languageOptions: {
            globals: {
                ...globals.browser,
                twemoji: "readonly",
                twemojiOptions: "readonly",
                emojis: "readonly",
                emotes: "readonly",
                username: "readonly",
                require: "readonly",
            },
            parserOptions: {
                 projectService: true,
            },
        },
    },
]);

