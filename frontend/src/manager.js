import $ from "jquery";

import { EventEmitter } from "events";
import { Menu } from "./menu.js";
import { Messages } from "./messages.js";
import { Info } from "./info.js";
import { Search } from "./search.js";
import { InputState } from "./inputstate.js";
import { ScreenState } from "./screenstate.js";
import { AudioNotifications } from "./components/audionotifs.js";

import { escapeHtml, flash, flashHook, containsStandaloneText } from "./utils.js";
import { displayInfo } from "./modals/infomodal.js";

export function manager(socket) {
    var eventBus = new EventEmitter();
    var inputState = new InputState();
    var screenState = new ScreenState();

    var rooms = new Map();
    var settings = {};
    var size = $( window ).width() <= 700 ? "mobile" : "desktop";
    var visibility = document.visibilityState;

    var menuInst = new Menu(eventBus, screenState, inputState, size, visibility);
    var messagesInst = new Messages(eventBus, screenState, inputState, size, visibility);
    var infoInst = new Info(eventBus, screenState, inputState, size, visibility);
    var searchInst = new Search(eventBus, screenState, inputState);
    var notifInst = new AudioNotifications(eventBus, size, visibility);

    // Ensure any server-generated messages are closeable.
    flashHook();

    // Check for application updates.
    function checkForUpdates() {
        $.getJSON(window.versionCheck, function( data ) {
            if (data.js != window.version) {
                window.version = data.js;
                flash( 'info', 'There is a new version of ' + window.appname + ' available. Refresh to upgrade!' );
            }
        });
    }

    setInterval(checkForUpdates, 1000 * 15);

    socket.on('connect', () => {
        // Let our various subsystems know we made a connection to the server.
        eventBus.emit('connected', {});

        // Ask for our profile and last settings so we can refresh where we left off.
        socket.emit('profile', {});
        socket.emit('preferences', {});
        socket.emit('lastsettings', {});

        // Ask for our list of rooms that we're in.
        socket.emit('roomlist', {});

        // Ask for any server MOTD or admin messages.
        socket.emit('motd', {});
    });

    socket.on('disconnect', () => {
        // Let our various subsystems know we lost our connection to the server.
        eventBus.emit('disconnected', {});
    });

    socket.on('reload', () => {
        // Server wants us to reload, probably to de-auth ourselves after a remote logout.
        window.location.reload();
    });

    $( window ).on( "resize", () => {
        const width = $( window ).width();
        const newSize = width <= 700 ? "mobile" : "desktop";

        if (newSize != size) {
            size = newSize;
            eventBus.emit('resize', size);
        }
    });

    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState != visibility) {
            visibility = document.visibilityState;
            eventBus.emit('updatevisibility', visibility);
        }
    });

    socket.on('welcome', (msg) => {
        var html = "";
        msg.rooms.forEach((result) => {
            var id = result.roomid;
            var type = result.type == "room" ? 'room' : 'avatar';

            html += '<div class="item" id="' + id + '">';
            html += '  <div class="icon ' + type + '">';
            html += '    <img src="' + result.icon + '" />';
            if (result.type == 'room') {
                html    += '    <div class="room-indicator">#</div>';
            }
            html += '  </div>';
            html += '  <div class="name-wrapper"><div class="name">' + escapeHtml(result.name) + '</div></div>';
            html += '</div>';
        });

        displayInfo(
            '<div class="welcome-message">' + msg.message + '</div><div class="results">' + html + '</div>',
            'okay!',
            () => {
                socket.emit('welcomeaccept', {});
            }
        );
    });

    socket.on('error', (msg) => {
        displayInfo(
            msg.error,
            'okay!',
        );
    })

    socket.on('roomlist', (msg) => {
        if (msg.rooms) {
            // First, track the rooms ourselves so we can handle notification generation.
            const newRooms = new Map();
            msg.rooms.forEach((room) => {
                newRooms.set(room.id, room);
            });
            rooms = newRooms;

            // Now, notify our various systems.
            menuInst.setRooms(msg.rooms);
            infoInst.setRooms(msg.rooms);
            messagesInst.setRooms(msg.rooms);
        }
        if (msg.counts) {
            menuInst.setBadges(msg.counts);
        }
        if (msg.selected) {
            menuInst.selectRoom(msg.selected);
        }
    });

    socket.on('lastsettings', (msg) => {
        settings = msg;
        menuInst.setLastSettings(msg);
        messagesInst.setLastSettings(msg);
        infoInst.setLastSettings(msg);
    });

    socket.on('profile', (msg) => {
        // This should never change, but if we have info about it, let's update anyway.
        window.username = msg.username;
        menuInst.setProfile(msg);
        messagesInst.setProfile(msg);
        infoInst.setProfile(msg);
    });

    socket.on('preferences', (msg) => {
        if (msg.color_scheme == "light") {
            $( "body" ).removeClass("dark").addClass("light");
        } else if (msg.color_scheme == "dark") {
            $( "body" ).removeClass("light").addClass("dark");
        } else {
            $( "body" ).removeClass("light").removeClass("dark");
        }
        menuInst.setPreferences(msg);
        messagesInst.setPreferences(msg);
        infoInst.setPreferences(msg);
        notifInst.setPreferences(msg);
    });

    socket.on('chathistory', (msg) => {
        if (msg.occupants) {
            messagesInst.setOccupants(msg.roomid, msg.occupants);
            infoInst.setOccupants(msg.roomid, msg.occupants);
        }
        messagesInst.updateHistory(msg.roomid, msg.history, msg.lastseen);
    });

    socket.on('chatactions', (msg) => {
        // First, regardless of the room, figure out if any notification sounds should be
        // generated from these messages.
        var roomType = undefined;
        if (rooms.has(msg.roomid)) {
            roomType = rooms.get(msg.roomid).type;
        }

        if (roomType) {
            msg.actions.forEach((message) => {
                if (message.action == "join") {
                    if (message.occupant.username != window.username) {
                        eventBus.emit("notification", {"action": "join", "type": roomType});
                    }
                } else if (message.action == "leave") {
                    if (message.occupant.username != window.username) {
                        eventBus.emit("notification", {"action": "leave", "type": roomType});
                    }
                } else if (message.action == "message") {
                    if (message.occupant.username == window.username) {
                        eventBus.emit("notification", {"action": "messageSend", "type": roomType})
                    } else {
                        const escaped = escapeHtml(message.details);
                        const actualuser = escapeHtml('@' + window.username);
                        if (containsStandaloneText(escaped, actualuser)) {
                            eventBus.emit("notification", {"action": "mention", "type": roomType});
                        } else {
                            eventBus.emit("notification", {"action": "messageReceive", "type": roomType});
                        }
                    }
                }
            });
        }

        // Now, notify various subsystems of new actions.
        messagesInst.updateActions(msg.roomid, msg.actions);
        menuInst.updateActions(msg.roomid, msg.actions);
        infoInst.updateActions(msg.roomid, msg.actions);
    });

    socket.on('searchrooms', (msg) => {
        searchInst.populateResults(msg.rooms);
    });

    socket.on('emotechanges', (msg) => {
        messagesInst.addEmotes(msg.additions);
        messagesInst.deleteEmotes(msg.deletions);
    });

    eventBus.on('selectroom', (roomid) => {
        settings.roomid = roomid;

        messagesInst.setRoom(roomid);
        infoInst.setRoom(roomid);
        socket.emit('updatesettings', settings);
        socket.emit('chathistory', {roomid: roomid});
    });

    eventBus.on('loadhistory', (info) => {
        socket.emit('chathistory', {roomid: info.roomid, before: info.before});
    });

    eventBus.on('loadactions', (info) => {
        socket.emit('chatactions', {roomid: info.roomid, after: info.after});
    });

    eventBus.on('updateinfo', (info) => {
        settings.info = info;

        socket.emit('updatesettings', settings);
    });

    eventBus.on('updateprofile', (profile) => {
        socket.emit('updateprofile', profile);
    });

    eventBus.on('updatepreferences', (preferences) => {
        socket.emit('updatepreferences', preferences);
    });

    eventBus.on('leaveroom', (roomid) => {
        socket.emit('leaveroom', {'roomid': roomid})

        messagesInst.closeRoom(roomid);
        infoInst.closeRoom(roomid);
        menuInst.closeRoom(roomid);
    });

    eventBus.on('joinroom', (roomoruserid) => {
        socket.emit('joinroom', {'roomid': roomoruserid})
    });

    eventBus.on('updateroom', (msg) => {
        socket.emit('updateroom', {'roomid': msg.roomid, 'details': msg.details});
    });

    eventBus.on('message', (msg) => {
        socket.emit('message', msg);
    });

    eventBus.on('searchrooms', (value) => {
        socket.emit('searchrooms', {'name': value})
    });

    eventBus.on('lastaction', (value) => {
        socket.emit('lastaction', value);
    });
}
