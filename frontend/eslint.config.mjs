import globals from "globals";
import { defineConfig } from "eslint/config";
import js from "@eslint/js";

export default defineConfig([
    {
        files: ["src/**/*.js"],
        plugins: {
            js,
        },
        extends: ["js/recommended"],
        rules: {
            "no-unused-vars": "warn",
            "no-undef": "warn",
            "no-prototype-builtins": "off",
        },
        languageOptions: {
            globals: {
                ...globals.browser,
                twemoji: "readonly",
                twemojiOptions: "readonly",
                emojis: "readonly",
                emotes: "readonly",
            },
        },
    },
]);

