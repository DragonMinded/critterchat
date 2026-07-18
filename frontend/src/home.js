import $ from "jquery";
import { hook } from "./extensions.js";

// Importing this enables linkify.
import * as linkify from "linkifyjs"; // eslint-disable-line @typescript-eslint/no-unused-vars

// Hook our custom jQuery extensions immediately.
hook();

import { escapeHtml } from "./utils";

$( document ).ready(function () {
    // Perform any emoji sanitization necessary.
    $('.convert-emoji').each( (_idx, elem) => {
        const text = $(elem).text();
        $(elem).html(escapeHtml(text));
    });
});
