import $ from "jquery";

import { EventEmitter } from "events";
import { Menu } from "./menu.js";
import { Messages } from "./messages.js";
import { Info } from "./info.js";
import { Search } from "./search.js";
import { InputState } from "./inputstate.js";
import { ScreenState } from "./screenstate.js";

import { escapeHtml, flash, flashHook } from "./utils.js";
import { displayInfo } from "./modals/infomodal.js";

export function manager(socket) {
    var eventBus = new EventEmitter();
    var inputState = new InputState();
    var screenState = new ScreenState();

    var settings = {};
    var size = $( window ).width() <= 700 ? "mobile" : "desktop";
    var visibility = document.visibilityState;

    var menuInst = new Menu(eventBus, screenState, inputState, size, visibility);
    var messagesInst = new Messages(eventBus, screenState, inputState, size, visibility);
    var infoInst = new Info(eventBus, screenState, inputState, size, visibility);
    var searchInst = new Search(eventBus, screenState, inputState);

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
        // Ask for our list of rooms that we're in.
        socket.emit('roomlist', {});

        // Ask for our profile and last settings so we can refresh where we left off.
        socket.emit('profile', {});
        socket.emit('preferences', {});
        socket.emit('lastsettings', {});

        // Ask for any server MOTD or admin messages.
        socket.emit('motd', {});
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
            var type = result['public'] ? 'room' : 'avatar';

            html += '<div class="item" id="' + id + '">';
            html += '  <div class="icon ' + type + '">';
            html += '    <img src="' + result.icon + '" />';
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
        menuInst.setRooms(msg.rooms);
        if (msg.counts) {
            menuInst.setBadges(msg.counts);
        }
        infoInst.setRooms(msg.rooms);
        if (msg.selected) {
            menuInst.selectRoom(msg.selected);
        }
        messagesInst.setRooms(msg.rooms);
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
        menuInst.setPreferences(msg);
        messagesInst.setPreferences(msg);
        infoInst.setPreferences(msg);
    });

    socket.on('chathistory', (msg) => {
        if (msg.occupants) {
            messagesInst.setOccupants(msg.roomid, msg.occupants);
            infoInst.setOccupants(msg.roomid, msg.occupants);
        }
        messagesInst.updateHistory(msg.roomid, msg.history, msg.lastseen);
    });

    socket.on('chatactions', (msg) => {
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

    eventBus.on('updateinfo', (info) => {
        settings.info = info;

        socket.emit('updatesettings', settings);
    });

    eventBus.on('updateprofile', (profile) => {
        socket.emit('updateprofile', profile);
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
