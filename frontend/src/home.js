import $ from "jquery";
import { hook } from "./config/extensions.js";

// Importing this enables linkify.
import * as linkify from "linkifyjs"; // eslint-disable-line no-unused-vars

// Hook our custom jQuery extensions immediately.
hook();

import { escapeHtml } from "./utils.js";

$( document ).ready(function () {
    // Perform any emoji sanitization necessary.
    $('.convert-emoji').each( (_idx, elem) => {
        const text = $(elem).text();
        $(elem).html(escapeHtml(text));
    });
});
