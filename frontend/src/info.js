import $ from "jquery";
import { escapeHtml } from "./utils.js";

class Info {
    constructor( eventBus, inputState ) {
        this.eventBus = eventBus;
        this.inputState = inputState;
        this.roomid = "";
        this.occupants = [];
        this.rooms = [];
        this.lastSettings = {};
        this.roomsLoaded = false;
        this.occupantsLoaded = false;
        this.lastSettingsLoaded = false;

        $( '#infotoggle' ).on( 'click', (event) => {
            event.preventDefault();

            this.inputState.setState("empty");
            if ($('div.container > div.info').hasClass('hidden')) {
                $('div.container > div.info').removeClass('hidden');
                this.lastSettings.info = "shown";
            } else {
                $('div.container > div.info').addClass('hidden');
                this.lastSettings.info = "hidden";
            }

            this.eventBus.emit('info', this.lastSettings.info);
        });

        $( '#confirm-leave-room, #confirm-leave-chat').on( 'click', (event) => {
            event.preventDefault();

            this.eventBus.emit('leaveroom', $( '#leave-room' ).attr('roomid'));
            $.modal.close();
        });

        $( '#cancel-leave-room, #cancel-leave-chat').on( 'click', (event) => {
            event.preventDefault();

            $.modal.close();
        });

        $( '#leave-room' ).on( 'click', (event) => {
            event.preventDefault();

            this.inputState.setState("empty");
            var roomid = $( '#leave-room' ).attr('roomid');
            this.rooms.forEach((room) => {
                if (room.id == roomid) {
                    if (room.type == 'room') {
                        $('#leave-room-form').modal();
                    } else {
                        $('#leave-chat-form').modal();
                    }
                }
            });
        });

        $( 'div.info > div.occupants' ).on( 'click', () => {
            this.inputState.setState("empty");
        });
    }

    setRooms( rooms ) {
        // Make a copy instead of keeping a reference, so we can safely mutate.
        this.rooms = rooms.filter(() => true);
        this.roomsLoaded = true;
    }

    setOccupants( roomid, occupants ) {
        if (roomid == this.roomid) {
            this.occupants = occupants.filter((occupant) => !occupant.inactive);
            this.occupants.sort((a, b) => { return a.nickname.localeCompare(b.nickname); });
            this.occupantsLoaded = true;

            if (this.roomsLoaded && this.occupantsLoaded) {
                this.drawOccupants();
            }
        }
    }

    updateActions( roomid, history ) {
        if (roomid != this.roomid) {
            // Must be an out of date lookup, ignore it.
            return;
        }

        // Figure out if it's a join or a leave.
        var changed = false;
        if (this.roomsLoaded && this.occupantsLoaded) {
            history.forEach((entry) => {
                if (entry.action == "join") {
                    this.occupants.push(entry.occupant);
                    changed = true;
                } else if (entry.action == "leave") {
                    this.occupants = this.occupants.filter((occupant) => occupant.id != entry.occupant.id);
                    changed = true;
                }
            });
        }

        if (changed) {
            this.occupants.sort((a, b) => { return a.nickname.localeCompare(b.nickname); });
            this.drawOccupants();
        }
    }

    drawOccupants() {
        var occupantElement = $('div.info > div.occupants')
        var scrollPos = occupantElement.scrollTop();
        occupantElement.empty();

        this.occupants.forEach((occupant) => {
            // Now, draw it fresh since it's not an update.
            var html = '<div class="item" id="' + occupant.id + '">';
            html    += '  <div class="icon avatar">';
            html    += '    <img src="' + occupant.icon + '" />';
            html    += '  </div>';
            html    += '  <div class="name-wrapper"><div class="name">' + escapeHtml(occupant.nickname) + '</div></div>';
            html    += '</div>';
            occupantElement.append(html);
        });

        occupantElement.scrollTop(scrollPos);
    }

    setLastSettings( settings ) {
        this.lastSettings = settings;
        this.lastSettingsLoaded = true;

        if (this.lastSettings.info == "shown") {
            $('div.container > div.info').removeClass('hidden');
        } else {
            $('div.container > div.info').addClass('hidden');
        }
    }

    setRoom( roomid ) {
        if (roomid != this.roomid) {
            this.occupants = [];
            this.occupantsLoaded = false;
            this.roomid = roomid;

            $('div.info > div.occupants').empty();
            $( '#leave-room' ).attr('roomid', roomid);
            this.rooms.forEach((room) => {
                if (room.id == roomid) {
                    var title;
                    if (room.type == "chat") {
                        if (room['public']) {
                            title = "Public group chat";
                        } else {
                            title = "Private chat";
                        }
                    } else {
                        if (room['public']) {
                            title = "Public room";
                        } else {
                            title = "Private room";
                        }
                    }
                    $( '#room-title' ).text(title);
                    if (room.type == 'room') {
                        $( '#leave-type' ).text('room');
                    } else {
                        $( '#leave-type' ).text('chat');
                    }
                }
            });
        }
    }

    closeRoom( roomid ) {
        if (roomid == this.roomid) {
            this.occupants = [];
            this.occupantsLoaded = false;
            this.roomid = "";

            $('div.info > div.occupants').empty();
            $( '#leave-room' ).attr('roomid', '');
        }
    }
}

export { Info };
