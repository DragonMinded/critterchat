import $ from "jquery";
import { io } from "socket.io-client";

// Importing this hooks it into jQuery.
import { modal } from "jquery-modal"; // eslint-disable-line no-unused-vars

import { manager } from "./manager.js";
import { hook } from "./extensions.js";

// Hook jQuery extensions immediately.
hook();

$( document ).ready(function () {
    // Connect to the backend.
    var socket = io.connect(location.protocol  + '//' + document.domain + ':' + location.port);

    // Set up chat manager to handle messages.
    manager(socket);
});
