import { Menu } from "./menu.js";

export function manager(socket) {
    var menuInst = new Menu(socket);

    socket.on('connect', function() {
        // Ask for our list of rooms that we're in.
        socket.emit('roomlist', {});
    });

    socket.on('reload', function() {
        // Server wants us to reload, probably to de-auth ourselves after a remote logout.
        window.location.reload();
    });

    socket.on('roomlist', function(msg) {
        menuInst.setRooms(msg.rooms);
    });
}
