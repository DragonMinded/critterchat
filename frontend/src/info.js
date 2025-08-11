import $ from "jquery";
import { escapeHtml } from "./utils.js";
import { ChatDetails } from "./modals/chatdetails.js";
import { displayWarning } from "./modals/warningmodal.js";

class Info {
    constructor( eventBus, screenState, inputState, initialSize ) {
        this.eventBus = eventBus;
        this.inputState = inputState;
        this.screenState = screenState;
        this.chatdetails = new ChatDetails( eventBus, inputState );
        this.size = initialSize;

        this.roomid = "";
        this.occupants = [];
        this.rooms = [];
        this.lastSettings = {};
        this.roomsLoaded = false;
        this.occupantsLoaded = false;
        this.infoLoaded = false;
        this.lastSettingsLoaded = false;

        $( '#infotoggle' ).on( 'click', (event) => {
            event.preventDefault();

            if (this.size == "mobile") {
                this.inputState.setState("empty");
                this.screenState.setState("info");
            } else {
                this.inputState.setState("empty");
                if ($('div.container > div.info').hasClass('hidden')) {
                    $('div.container > div.info').removeClass('hidden');
                    this.lastSettings.info = "shown";
                } else {
                    $('div.container > div.info').addClass('hidden');
                    this.lastSettings.info = "hidden";
                }

                this.eventBus.emit('updateinfo', this.lastSettings.info);
            }
        });

        $( '#leave-room' ).on( 'click', (event) => {
            event.preventDefault();

            this.inputState.setState("empty");
            var roomid = $( '#leave-room' ).attr('roomid');
            this.rooms.forEach((room) => {
                if (room.id == roomid) {
                    displayWarning(
                        room.type == 'room' ?
                            'Leaving this room will mean you no longer receive messages from the other members. You can still ' +
                            're-join this room in the future by searching for the room\'s name and clicking "join".' :
                            'Leaving this chat will mean you no longer receive messages from the other chatter. You can still ' +
                            're-join this chat in the future by searching for the chatter\'s name and clicking "message".',
                        'yes, leave',
                        'no, stay here',
                        () => {
                            this.eventBus.emit('leaveroom', $( '#leave-room' ).attr('roomid'));
                        }
                    );
                }
            });
        });

        $( '#edit-info' ).on( 'click', (event) => {
            event.preventDefault();

            this.inputState.setState("empty");
            var roomid = $( '#leave-room' ).attr('roomid');
            this.chatdetails.display( roomid );
        });

        $( 'div.info > div.occupants' ).on( 'click', () => {
            this.inputState.setState("empty");
        });

        $( 'div.info div.title-wrapper' ).hide();
        $( 'div.info div.actions' ).hide();

        $( 'div.info div.back' ).on( 'click', (event) => {
            event.preventDefault();

            this.inputState.setState("empty");
            this.screenState.setState("chat");
        });

        // Set up dynamic mobile detection.
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
            $( 'div.info div.back' ).show();
            if (this.screenState.current == "info") {
                $( 'div.container > div.info' ).removeClass('hidden').addClass('full');
            } else {
                $( 'div.container > div.info' ).addClass('hidden').addClass('full');
            }
        } else {
            $( 'div.info div.back' ).hide();
            if (this.lastSettings.info == "shown") {
                $( 'div.container > div.info' ).removeClass('hidden').removeClass('full');
            } else {
                $( 'div.container > div.info' ).addClass('hidden').removeClass('full');
            }
        }
    }

    setRooms( rooms ) {
        // Make a copy instead of keeping a reference, so we can safely mutate.
        this.rooms = rooms.filter(() => true);
        this.roomsLoaded = true;
        if (this.roomid) {
            if (!this.infoLoaded) {
                this.setRoom(this.roomid);
            } else {
                this.updateRoom(this.roomid);
            }
        }
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
                } else if (entry.action == "change_profile") {
                    this.occupants.forEach((occupant) => {
                        if (occupant.id == entry.occupant.id) {
                            occupant.nickname = entry.occupant.nickname;
                            occupant.icon = entry.occupant.icon;
                        }
                    });
                    $('div.info > div.occupants div.item#' + entry.occupant.id + ' div.name').html(escapeHtml(entry.occupant.nickname));
                    $('div.info > div.occupants div.item#' + entry.occupant.id + ' div.icon img').attr('src', entry.occupant.icon);
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

        if (this.size != "mobile") {
            if (this.lastSettings.info == "shown") {
                $('div.container > div.info').removeClass('hidden').removeClass('full');
            } else {
                $('div.container > div.info').addClass('hidden').removeClass('full');
            }
        }
    }

    setRoom( roomid ) {
        if (roomid != this.roomid || !this.infoLoaded) {
            this.occupants = [];
            this.occupantsLoaded = false;
            this.roomid = roomid;

            $('div.info > div.occupants').empty();
            var updated = false;

            this.rooms.forEach((room) => {
                if (room.id == roomid) {
                    var title;
                    var iconType;
                    if (room.type == "chat") {
                        if (room['public']) {
                            title = "Public group chat";
                            iconType = 'room';
                        } else {
                            title = "Private chat";
                            iconType = 'avatar';
                        }
                    } else {
                        if (room['public']) {
                            title = "Public room";
                            iconType = 'room';
                        } else {
                            title = "Private room";
                            iconType = 'avatar';
                        }
                    }
                    $( '#room-title' ).text(title);
                    if (room.type == 'room') {
                        $( '#leave-type' ).text('room');
                    } else {
                        $( '#leave-type' ).text('chat');
                    }

                    $( 'div.info div.title-wrapper' ).show();
                    $( 'div.info div.actions' ).show();
                    $( 'div.chat div.icon' ).removeClass('room').removeClass('avatar').addClass(iconType);
                    $( 'div.chat div.icon img' ).attr('src', room.icon);
                    $( 'div.chat div.icon' ).removeClass('hidden');
                    $( 'div.chat div.title' ).html(escapeHtml(room.name));
                    $( 'div.chat div.topic' ).html(escapeHtml(room.topic));
                    $( '#leave-room' ).attr('roomid', roomid);
                    $( '#edit-info' ).attr('roomid', roomid);

                    updated = true;

                    this.chatdetails.setRoom(room);
                }
            });

            // Only set this if we updated, so if we leave a room, refesh, and then rejoin
            // that room, we don't accidentally ignore setting its info.
            if (updated) {
                this.infoLoaded = true;
            }
        }
    }

    updateRoom( roomid ) {
        if (roomid == this.roomid && this.infoLoaded) {
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

                    $( 'div.chat div.title' ).html(escapeHtml(room.name));
                    $( 'div.chat div.topic' ).html(escapeHtml(room.topic));
                    this.chatdetails.setRoom(room);
                }
            });
        }
    }

    closeRoom( roomid ) {
        if (roomid == this.roomid) {
            this.chatdetails.closeRoom(roomid);
            this.occupants = [];
            this.occupantsLoaded = false;
            this.infoLoaded = false;
            this.roomid = "";

            $( 'div.info > div.occupants' ).empty();
            $( '#leave-room' ).attr('roomid', '');
            $( '#edit-info' ).attr('roomid', '');
            $( 'div.chat div.title' ).html('&nbsp;');
            $( 'div.chat div.topic' ).html('&nbsp;');
            $( 'div.info div.title-wrapper' ).hide();
            $( 'div.info div.actions' ).hide();
        }
    }
}

export { Info };
