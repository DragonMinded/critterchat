import $ from "jquery";
import { escapeHtml } from "./utils.js";
import { EditProfile } from "./modals/editprofile.js";
import { displayWarning } from "./modals/warningmodal.js";

class Menu {
    constructor( eventBus, screenState, inputState, initialSize ) {
        this.eventBus = eventBus;
        this.screenState = screenState;
        this.inputState = inputState;
        this.editProfile = new EditProfile( eventBus, inputState );
        this.size = initialSize;
        this.title = document.title;

        this.rooms = [];
        this.selected = "";
        this.lastSettings = {};
        this.roomsLoaded = false;
        this.lastSettingsLoaded = false;

        $( 'div.menu > div.rooms' ).on( 'click', () => {
            this.inputState.setState("empty");
        });

        $( '#edit-profile' ).on( 'click', (event) => {
            event.preventDefault();

            this.inputState.setState("empty");
            this.editProfile.display();
        });

        $( '#log-out' ).on( 'click', (event) => {
            event.preventDefault();

            this.inputState.setState("empty");
            displayWarning(
                'Are you sure you want to log out?',
                'yes, log out',
                'no, stay here',
                () => {
                    window.location.href = "/logout";
                }
            );
        });

        // Set up the mobile back button.
        $( 'div.top-info div.back' ).on( 'click', (event) => {
            event.preventDefault();

            this.inputState.setState("empty");
            this.screenState.setState("menu");
        });

        eventBus.on( 'resize', (newSize) => {
            this.size = newSize;
            this.updateSize();
        });

        this.screenState.registerStateChangeCallback(() => {
            this.updateSize();
        });

        this.updateSize();
    }

    updateSize() {
        if (this.size == "mobile") {
            $( 'div.top-info div.back' ).show();
            if (this.screenState.current == "menu") {
                $( 'div.container > div.menu' ).removeClass('hidden').addClass('full');
            } else {
                $( 'div.container > div.menu' ).addClass('hidden').addClass('full');
            }
        } else {
            $( 'div.top-info div.back' ).hide();
            $( 'div.container > div.menu' ).removeClass('hidden').removeClass('full');
        }
    }

    setRooms( rooms ) {
        // Redraw if the room length or ordering changed, otherwise refresh in place.
        var needsEmpty = false;
        if (rooms.length == this.rooms.length) {
            for (var i = 0; i < rooms.length; i++) {
                if (rooms[i].id != this.rooms[i].id) {
                    needsEmpty = true;
                    break;
                }
            }
        } else {
            needsEmpty = true;
        }

        // Make sure to preserve badge counts.
        var counts = {};
        this.rooms.forEach((room) => {
            counts[room.id] = room.count;
        });

        // Make a copy instead of holding onto a reference, so we can mutate.
        this.rooms = rooms.filter(() => true);
        this.roomsLoaded = true;

        // Copy badge counts over.
        this.rooms.forEach((room) => {
            room.count = counts[room.id];
        });

        // If we re-arranged anything, nuke our existing.
        var scrollPos = $('div.menu > div.rooms').scrollTop();
        if (needsEmpty) {
            $('div.menu > div.rooms').empty();
        }

        // Draw, and then select the room.
        this.rooms.forEach((room) => this.drawRoom(room));
        $('div.menu > div.rooms').scrollTop(scrollPos);

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

    setProfile( profile ) {
        this.editProfile.setProfile( profile );
    }

    drawRoom( room ) {
        // First, see if this is an update.
        var conversations = $('div.menu > div.rooms');
        var drawnRoom = conversations.find('div.item#' + room.id);
        if (drawnRoom.length > 0) {
            drawnRoom.find('.icon img').attr('src', room.icon);
            drawnRoom.find('.name').html(escapeHtml(room.name));
        } else {
            // Now, draw it fresh since it's not an update.
            var type = room['public'] ? 'room' : 'avatar';
            var html = '<div class="item" id="' + room.id + '">';
            html    += '  <div class="icon ' + type + '">';
            html    += '    <img src="' + room.icon + '" />';
            if (room.count) {
                html    += '    <div class="badge"><div class="count">' + room.count + '</div>';
            } else {
                html    += '    <div class="badge empty"><div class="count"></div>';
            }
            html    += '    </div>';
            html    += '  </div>';
            html    += '  <div class="name-wrapper"><div class="name">' + escapeHtml(room.name) + '</div></div>';
            html    += '</div>';
            conversations.append(html);

            $('div.menu > div.rooms div.item#' + room.id).on('click', (event) => {
                event.stopPropagation();
                event.stopImmediatePropagation();

                this.inputState.setState("empty");

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

        if (found) {
            this.screenState.setState("chat");
        }

        if (found && roomid != this.selected) {
            this.selected = roomid;
            this.updateSelected();
            this.clearBadges(roomid);

            this.eventBus.emit('selectroom', roomid);
        }

        $('input#message').focus();
    }

    closeRoom( roomid ) {
        if (this.selected == roomid ) {
            this.selected = "";

            var conversations = $('div.menu > div.rooms');
            conversations.find('div.item#' + roomid).remove();

            this.rooms = this.rooms.filter((room) => room.id != roomid);

            this.screenState.setState("menu");
        }

        this.updateSelected();
    }

    updateSelected() {
        $('div.menu > div.rooms div.item').removeClass('selected');
        if (this.selected) {
            $('div.menu > div.rooms div.item#' + this.selected).addClass('selected');
        }
    }

    updateActions( roomid, actions ) {
        var count = 0;
        actions.forEach((action) => {
            if (
                action.action == "message" ||
                action.action == "join" ||
                action.action == "leave" ||
                action.action == "change_info"
            ) {
                count += 1;
            }
        });
        this.updateBadges( roomid, count );
        this.updateTitleBadge();
    }

    updateBadges( roomid, newactions ) {
        if (roomid == this.selected) {
            return;
        }
        if (newactions == 0) {
            return;
        }

        // Find the room to update
        var conversations = $('div.menu > div.rooms');
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

            var intCount = parseInt(count) + newactions;
            var text;
            if (intCount > 9) {
                text = '!!';
            } else {
                text = intCount.toString();
            }

            badge.text(text);
            this.rooms.forEach((room) => {
                if (room.id == roomid) {
                    room.count = text;
                }
            });
        }
    }

    setBadges( badges ) {
        if (this.roomsLoaded) {
            badges.forEach((obj) => {
                this.clearBadges(obj.roomid);
                if (obj.count) {
                    this.updateBadges(obj.roomid, obj.count);
                }
            });

            this.updateTitleBadge();
        }
    }

    clearBadges( roomid ) {
        // Find the room to update
        var conversations = $('div.menu > div.rooms');
        var drawnRoom = conversations.find('div.item#' + roomid);
        if (drawnRoom.length > 0) {
            drawnRoom.find('.icon .badge').addClass('empty');
            drawnRoom.find('.icon .badge .count').text("");
            this.rooms.forEach((room) => {
                if (room.id == roomid) {
                    room.count = '';
                }
            });
        }

        this.updateTitleBadge();
    }

    updateTitleBadge() {
        var hasBadges = false;
        this.rooms.forEach((room) => {
            if (room.count) {
                hasBadges = true;
            }
        });

        if (hasBadges) {
            document.title = this.title + " [\u2605]";
        } else {
            document.title = this.title;
        }
    }
}

export { Menu };
