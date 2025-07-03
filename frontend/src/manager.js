import { EventEmitter } from "events";
import { Menu } from "./menu.js";
import { Messages } from "./messages.js";
import { Info } from "./info.js";
import { Search } from "./search.js";

export function manager(socket) {
    var eventBus = new EventEmitter();
    var menuInst = new Menu(eventBus);
    var messagesInst = new Messages(eventBus);
    var infoInst = new Info(eventBus);
    var searchInst = new Search(eventBus);
    var settings = {};

    socket.on('connect', () => {
        // Ask for our list of rooms that we're in.
        socket.emit('roomlist', {});

        // Ask for our last settings so we can refresh where we left off.
        socket.emit('lastsettings', {});
    });

    socket.on('reload', () => {
        // Server wants us to reload, probably to de-auth ourselves after a remote logout.
        window.location.reload();
    });

    socket.on('roomlist', (msg) => {
        menuInst.setRooms(msg.rooms);
        infoInst.setRooms(msg.rooms);
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

    socket.on('chathistory', (msg) => {
        messagesInst.updateHistory(msg.roomid, msg.history);
    });

    socket.on('chatactions', (msg) => {
        messagesInst.updateHistory(msg.roomid, msg.actions);
        menuInst.updateBadges(msg.roomid, msg.actions);
    });

    socket.on('searchrooms', (msg) => {
        searchInst.populateResults(msg.rooms);
    });

    eventBus.on('room', (roomid) => {
        settings.roomid = roomid;

        messagesInst.setRoom(roomid);
        infoInst.setRoom(roomid);
        socket.emit('updatesettings', settings);
        socket.emit('chathistory', {roomid: roomid});
    });

    eventBus.on('info', (info) => {
        settings.info = info;

        socket.emit('updatesettings', settings);
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

    eventBus.on('message', (msg) => {
        socket.emit('message', msg);
    });

    eventBus.on('searchrooms', (value) => {
        socket.emit('searchrooms', {'name': value})
    })
}
