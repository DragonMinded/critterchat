import $ from "jquery";
import { escapeHtml } from "./utils.js";

class Menu {
    constructor( eventBus ) {
        this.eventBus = eventBus;
        this.rooms = [];
        this.selected = "";
        this.lastSettings = {};
        this.roomsLoaded = false;
        this.lastSettingsLoaded = false;
    }

    setRooms( rooms ) {
        this.rooms = rooms;
        this.roomsLoaded = true;

        this.rooms.forEach((room, i) => this.drawRoom(room));

        if (this.lastSettingsLoaded) {
            this.selectRoom(this.lastSettings.roomid);
        }
    }

    setLastSettings( settings ) {
        this.lastSettings = settings;
        this.lastSettingsLoaded = true;

        if (this.roomsLoaded) {
            this.selectRoom(this.lastSettings.roomid);
        }
    }

    drawRoom( room ) {
        // First, see if this is an update.
        var conversations = $('div.menu > div.conversations');
        var drawnRoom = conversations.find('div.item#' + room.id);
        if (drawnRoom.length > 0) {
            drawnRoom.find('.icon img').attr('src', room.icon);
            drawnRoom.find('.name').html(escapeHtml(room.name));
        } else {
            // Now, draw it fresh since it's not an update.
            var html = '<div class="item" id="' + room.id + '">';
            html    += '  <div class="icon">';
            html    += '    <img src="' + room.icon + '" />';
            html    += '    <div class="badge empty">';
            html    += '    </div>';
            html    += '  </div>';
            html    += '  <div class="name-wrapper"><div class="name">' + escapeHtml(room.name) + '</div></div>';
            html    += '</div>';
            conversations.append(html);

            $('div.menu > div.conversations div.item#' + room.id).on('click', (event) => {
                event.stopPropagation();
                event.stopImmediatePropagation();

                var id = $(event.currentTarget).attr('id')
                this.selectRoom( id );
            });
        }

        this.updateSelected();
    }

    selectRoom( roomid ) {
        var found = false;
        for (const room of this.rooms) {
            if (room.id == roomid) {
                found = true;
                break;
            }
        }

        if (found && roomid != this.selected) {
            this.selected = roomid;
            this.updateSelected();

            this.eventBus.emit('room', roomid);
        }
    }

    updateSelected() {
        $('div.menu > div.conversations div.item').removeClass('selected');
        if (this.selected) {
            $('div.menu > div.conversations div.item#' + this.selected).addClass('selected');
        }
    }

    updateBadges( roomid, actions ) {
        // TODO: Need to figure out if this is for a room we're not in and update the
        // badge for any new entries received.
    };
}

export { Menu };
