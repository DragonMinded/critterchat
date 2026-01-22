import $ from "jquery";

// Run the jQuery modal hook to install jquery-modal
import { modal } from "./jquery-modal/jquery.modal.js";
modal();

import { manager } from "./manager.js";
import { hook } from "./config/extensions.js";
import { Socket } from "./components/socket.js";

// Importing this enables linkify.
import * as linkify from "linkifyjs"; // eslint-disable-line no-unused-vars

// Hook our custom jQuery extensions immediately.
hook();

$( document ).ready(function () {
    // Connect to the backend.
    var socket = new Socket(location.protocol  + '//' + document.domain + ':' + location.port);

    // Set up chat manager to handle messages.
    manager(socket);
});
