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

        $( '#search-chat' ).on( 'click', (event) => {
            event.preventDefault();
            $('#search-form').modal();
        });
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
            html    += '    <div class="badge empty"><div class="count"></div>';
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
            this.clearBadges(roomid);

            this.eventBus.emit('room', roomid);
        }
    }

    closeRoom( roomid ) {
        if (this.selected == roomid ) {
            this.selected = "";

            var conversations = $('div.menu > div.conversations');
            conversations.find('div.item#' + roomid).remove();

            for (var i = 0; i < this.rooms.length; i++) {
                if (this.rooms[i].id == roomid) {
                    this.rooms.splice(i, 1);
                    break;
                }
            }
        }

        this.updateSelected();
    }

    updateSelected() {
        $('div.menu > div.conversations div.item').removeClass('selected');
        if (this.selected) {
            $('div.menu > div.conversations div.item#' + this.selected).addClass('selected');
        }
    }

    updateBadges( roomid, actions ) {
        if (roomid == this.selected) {
            return;
        }

        // Find the room to update
        var conversations = $('div.menu > div.conversations');
        var drawnRoom = conversations.find('div.item#' + roomid);
        if (drawnRoom.length > 0) {
            drawnRoom.find('.icon .badge').removeClass('empty');

            var badge = drawnRoom.find('.icon .badge .count');
            var count = badge.text().trim();
            if (count == "!!") {
                // Already at the max.
                return;
            }
            if (count == "") {
                count = "0";
            }

            var intCount = parseInt(count) + actions.length;
            if (intCount > 9) {
                badge.text('!!');
            } else {
                badge.text(intCount.toString());
            }
        }
    }

    clearBadges( roomid ) {
        // Find the room to update
        var conversations = $('div.menu > div.conversations');
        var drawnRoom = conversations.find('div.item#' + roomid);
        if (drawnRoom.length > 0) {
            drawnRoom.find('.icon .badge').addClass('empty');
            drawnRoom.find('.icon .badge .count').text("");
        }
    }
}

export { Menu };
