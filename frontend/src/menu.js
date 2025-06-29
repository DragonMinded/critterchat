import $ from "jquery";
import { escapehtml } from "./utils.js";


class Menu {
    constructor( socket ) {
        this.socket = socket;
        this.rooms = [];
        this.lastSettings = {};
        this.roomsLoaded = false;
        this.lastSettingsLoaded = false;
    }

    setRooms( rooms ) {
        this.rooms = rooms;
        this.roomsLoaded = true;

        this.rooms.forEach((room, i) => this.drawRoom(room));
    }

    setLastSettings( settings ) {
        this.lastSettings = settings;
        this.lastSettingsLoaded = true;
    }

    drawRoom( room ) {
        // First, see if this is an update.
        var conversations = $('div.menu > div.conversations');
        var drawnRoom = conversations.find('div.item#' + room.id);
        if (drawnRoom.length > 0) {
            drawnRoom.find('.icon img').attr('src', room.icon);
            drawnRoom.find('.name').html(escapehtml(room.name));
        } else {
            // Now, draw it fresh since it's not an update.
            var html  = '<div class="item" id="' + room.id + '">';
            html += '  <div class="icon">';
            html += '    <img src="' + room.icon + '" />';
            html += '    <div class="badge empty">';
            html += '    </div>';
            html += '  </div>';
            html += '  <div class="name">' + escapehtml(room.name) + '</div>';
            html += '</div>';
            conversations.append(html);
        }
    }
}

export { Menu };
