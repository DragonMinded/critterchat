import { EventEmitter } from "events";
import { Menu } from "./menu.js";
import { Messages } from "./messages.js";
import { Info } from "./info.js";
import { Search } from "./search.js";
import { InputState } from "./inputstate.js";

import { escapeHtml } from "./utils.js";
import { displayInfo } from "./modals/infomodal.js";

export function manager(socket) {
    var eventBus = new EventEmitter();
    var inputState = new InputState();
    var menuInst = new Menu(eventBus, inputState);
    var messagesInst = new Messages(eventBus, inputState);
    var infoInst = new Info(eventBus, inputState);
    var searchInst = new Search(eventBus, inputState);
    var settings = {};

    socket.on('connect', () => {
        // Ask for our list of rooms that we're in.
        socket.emit('roomlist', {});

        // Ask for our profile and last settings so we can refresh where we left off.
        socket.emit('profile', {});
        socket.emit('lastsettings', {});

        // Ask for any server MOTD or admin messages.
        socket.emit('motd', {});
    });

    socket.on('reload', () => {
        // Server wants us to reload, probably to de-auth ourselves after a remote logout.
        window.location.reload();
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
    });

    socket.on('chathistory', (msg) => {
        messagesInst.setOccupants(msg.roomid, msg.occupants);
        infoInst.setOccupants(msg.roomid, msg.occupants);
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
