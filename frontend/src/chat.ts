import $ from "jquery";

// Run the jQuery modal hook to install jquery-modal
import { modal } from "./jquery-modal/jquery.modal";
modal();

import { manager } from "./manager";
import { hook } from "./extensions";
import { Socket } from "./components/socket";

// Importing this enables linkify.
import * as linkify from "linkifyjs"; // eslint-disable-line @typescript-eslint/no-unused-vars

// Hook our custom jQuery extensions immediately.
hook();

$( document ).ready(function () {
    // Connect to the backend.
    const socket = new Socket(location.protocol + '//' + document.domain + ':' + location.port);

    // Set up chat manager to handle messages.
    manager(socket);
});
