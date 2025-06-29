import { io } from "socket.io-client";

import { manager } from "./manager.js";

// Connect to the backend.
var socket = io.connect(location.protocol  + '//' + document.domain + ':' + location.port);

// Set up chat manager to handle messages.
manager(socket);
