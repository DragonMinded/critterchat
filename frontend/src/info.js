import $ from "jquery";
import linkifyHtml from "linkify-html";

import { escapeHtml } from "./utils.js";
import { ChatDetails } from "./modals/chatdetails.js";
import { displayWarning } from "./modals/warningmodal.js";

const linkifyOptions = { defaultProtocol: "http", target: "_blank", validate: { email: () => false } };

/**
 * The class responsible for the right hand menu. This also generates room leave request events
 * when the user clicks the leave room button and confirms their intention. It also manages the
 * chat details popover which allows users to edit the nickname, topic and icon of the room when
 * they have appropriate permission to do so. It does this by ferrying server information that's
 * relevant onward to the component that manages the popover.
 */
class Info {
    constructor( eventBus, screenState, inputState, initialSize, initialVisibility ) {
        this.eventBus = eventBus;
        this.inputState = inputState;
        this.screenState = screenState;
        this.chatdetails = new ChatDetails( eventBus, inputState );
        this.size = initialSize;
        this.visibility = initialVisibility;

        this.roomid = "";
        this.roomType = "chat";
        this.moderated = false;
        this.occupants = [];
        this.rooms = [];
        this.lastSettings = {};
        this.roomsLoaded = false;
        this.occupantsLoaded = false;
        this.infoLoaded = false;
        this.lastSettingsLoaded = false;

        $( '#infotoggle' ).on( 'click', (event) => {
            event.preventDefault();

            this._infoToggle();
        });

        $( 'div.top-info div.info' ).on( 'click', (event) => {
            event.preventDefault();

            this._infoToggle();
        });

        $( '#leave-room' ).on( 'click', (event) => {
            event.preventDefault();

            this.inputState.setState("empty");
            var roomid = $( '#leave-room' ).attr('roomid');
            this.rooms.forEach((room) => {
                if (room.id == roomid) {
                    var msg = "";

                    if (room.type == "room") {
                        msg =(
                            'Leaving this room will mean you no longer receive messages from the other members. You can still ' +
                            're-join this room in the future by searching for the room\'s name and clicking "join".'
                        );
                    } else if(room.type == "chat") {
                        msg =(
                            'Leaving this chat will mean you no longer receive messages from the other chatters. You can still ' +
                            're-join this chat in the future if you are re-invited to the chat.'
                        );
                    } else {
                        // This is a 1:1 conversation, you can always reopen these.
                        this.eventBus.emit('leaveroom', $( '#leave-room' ).attr('roomid'));
                        return;
                    }

                    displayWarning(
                        msg,
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
            this._updateSize();
        });

        this.screenState.registerStateChangeCallback(() => {
            this._updateSize();
        });

        this._updateSize();
    }

    /**
     * Called whenever the manager notifies us that our screen size has moved from desktop to mobile
     * or mobile to desktop. We use this to reflow whether we're pinned to the right side or possibly
     * displayed as a full-size panel.
     */
    _updateSize() {
        if (this.size == "mobile") {
            $( 'div.info div.back' ).show();
            $( 'div.top-info div.info' ).show();
            $( 'div.chat form.actions div.info' ).hide();
            if (this.screenState.current == "info") {
                $( 'div.container > div.info' ).removeClass('hidden').addClass('full');
            } else {
                $( 'div.container > div.info' ).addClass('hidden').addClass('full');
            }
        } else {
            $( 'div.info div.back' ).hide();
            $( 'div.top-info div.info' ).hide();
            $( 'div.chat form.actions div.info' ).show();
            if (this.lastSettings.info == "shown") {
                $( 'div.container > div.info' ).removeClass('hidden').removeClass('full');
            } else {
                $( 'div.container > div.info' ).addClass('hidden').removeClass('full');
            }
        }
    }

    /**
     * Called whenever one of the info buttons is clicked.
     */
    _infoToggle() {
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
    }

    /**
     * Called every time the server informs us that our profile was updated, as well as once every
     * connection success or reconnect. We don't care about this event but a handler was placed
     * here for consistency across top-level components.
     */
    setProfile( _profile ) {
        // This page intentionally left blank.
    }

    /**
     * Called every time the server informs us that preferences were updated, as well as once every
     * connection success or reconnect. We don't care about this event but a handler was placed
     * here for consistency across top-level components.
     */
    setPreferences( _preferences ) {
        // This page intentionally left blank.
    }

    /**
     * Called whenever the manager informs us of an updated room list from the server. The room list
     * is always absolute and includes all relevant rooms that we're in, ordered by last update newest
     * to oldest. We don't really care much about most of the info, but we do use this to keep a map
     * of room ID to various details since we manage the top info panel above the chat and want to
     * make sure it's kept up-to-date with the correct topic, name and icon.
     */
    setRooms( rooms ) {
        // Make a copy instead of keeping a reference, so we can safely mutate.
        this.rooms = rooms.filter(() => true);
        this.roomsLoaded = true;
        if (this.roomid) {
            if (!this.infoLoaded) {
                this.setRoom(this.roomid);
            } else {
                this._updateRoom(this.roomid);
            }
        }
    }

    /**
     * Called whenever the manager informs us of room occupants for a given room. We only care about
     * occupants for the room we're in, so ignore any out-of-date notifications for rooms we have
     * clicked away from.
     */
    setOccupants( roomid, occupants ) {
        if (roomid == this.roomid) {
            // Make a copy of the occupants so we can mess with it later if needed.
            this.occupants = occupants.filter((_occupant) => true);
            this.occupants.sort((a, b) => {
                if (this.roomType != "dm") {
                    const aSort = this._computeSortOrder(a);
                    const bSort = this._computeSortOrder(b);

                    if (aSort != bSort) {
                        return aSort - bSort;
                    }
                }

                return a.nickname.localeCompare(b.nickname);
            });
            this.occupantsLoaded = true;

            if (this.roomsLoaded && this.occupantsLoaded) {
                this._drawOccupants();
            }
        }
    }

    /**
     * Called whenever new actions are sent from the server to inform us that an action occurred.
     * We use this to keep our occupant list in sync by tracking joins and leaves so we can avoid
     * having to refresh the whole list every time it changes.
     */
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
                    if (this.roomType != "dm") {
                        this.occupants.push(entry.occupant);
                        changed = true;
                    } else {
                        // This has the subtle bug of if you message somebody who was deactivated and they
                        // also had previously been in your DM but closed it, it will show them as activated
                        // again until you refresh or navigate away and back. This is a rare enough occurance
                        // that I'm not worried about it.
                        this.occupants.forEach((occupant) => {
                            if (occupant.id == entry.occupant.id) {
                                occupant.inactive = false;
                                changed = true;
                            }
                        });
                    }
                } else if (entry.action == "leave") {
                    if (this.roomType != "dm") {
                        this.occupants = this.occupants.filter((occupant) => occupant.id != entry.occupant.id);
                        changed = true;
                    } else {
                        this.occupants.forEach((occupant) => {
                            if (occupant.id == entry.occupant.id) {
                                occupant.inactive = true;
                                changed = true;
                            }
                        });
                    }
                } else if (entry.action == "change_profile") {
                    this.occupants.forEach((occupant) => {
                        if (occupant.id == entry.occupant.id) {
                            occupant.nickname = entry.occupant.nickname;
                            occupant.icon = entry.occupant.icon;
                        }
                    });
                    $('div.info > div.occupants div.item#' + entry.occupant.id + ' div.name').html(escapeHtml(entry.occupant.nickname));
                    $('div.info > div.occupants div.item#' + entry.occupant.id + ' div.icon img').attr('src', entry.occupant.icon);
                } else if (entry.action == "change_users") {
                    const newOccupants = new Map();
                    entry.details.occupants.forEach((occupant) => {
                        newOccupants.set(occupant.id, occupant);
                    });

                    this.occupants.forEach((occupant) => {
                        if (newOccupants.has(occupant.id)) {
                            const newOccupant = newOccupants.get(occupant.id);
                            occupant.moderator = newOccupant.moderator;
                            occupant.inactive = newOccupant.inactive;
                        }
                    });
                    changed = true;
                } else if (entry.action == "change_info") {
                    this.moderated = entry.details.moderated;
                    changed = true;
                }
            });
        }

        if (changed) {
            this.occupants.sort((a, b) => {
                if (this.roomType != "dm") {
                    const aSort = this._computeSortOrder(a);
                    const bSort = this._computeSortOrder(b);

                    if (aSort != bSort) {
                        return aSort - bSort;
                    }
                }

                return a.nickname.localeCompare(b.nickname);
            });
            this._drawOccupants();
        }
    }

    /**
     * Called by sort function to determine sort order of user attributes.
     */
    _computeSortOrder(occupant) {
        if (this.roomType != "dm") {
            if (occupant.inactive) {
                return 2;
            }
        }

        if (this.moderated) {
            if (occupant.moderator) {
                return 0;
            }
        }

        return 1;
    }

    /**
     * Update the DOM to include a mirror of our known occupants for a room. We always maintain the
     * occupant list sorted alphabetically by nickname, so this function simply makes sure the right
     * names are in the right order.
     */
    _drawOccupants() {
        var occupantElement = $('div.info > div.occupants')
        var scrollPos = occupantElement.scrollTop();
        occupantElement.empty();

        this.occupants.forEach((occupant) => {
            // Now, draw it fresh since it's not an update.
            var cls = "item";
            if (occupant.inactive) {
                cls += " faded";
            }

            var html = '<div class="' + cls + '" id="' + occupant.id + '">';
            html    += '  <div class="icon avatar">';
            html    += '    <img src="' + occupant.icon + '" />';
            html    += '  </div>';
            html    += '  <div class="name-wrapper"><div class="name">' + escapeHtml(occupant.nickname) + '</div></div>';
            html    += '</div>';
            occupantElement.append(html);

            $('div.info > div.occupants div.item#' + occupant.id).on('click', (event) => {
                event.stopPropagation();
                event.stopImmediatePropagation();

                this.inputState.setState("empty");

                var id = $(event.currentTarget).attr('id')
                this.eventBus.emit('displayprofile', id);
            });

        });

        occupantElement.scrollTop(scrollPos);
    }

    /**
     * Called whenever settings are received from the server. This only happens upon a successful
     * connection and not any time after, so use this to do the initial info panel hide or show.
     * This lets us preserve the info panel visibility across reloads/refreshes. In mobile mode
     * this has no effect on the current page layout because the menu/chat/info panes are turned
     * into screens that can be transitioned to by tapping various buttons on the screens themselves.
     */
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

    /**
     * Called when the manager informs us that the user has selected a new room, or when a new
     * room has been selected for the user (such as selecting a room after joining it). In either
     * case, all we care about is updating the info panel to reflect the newly-selected room.
     */
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
                        title = "Private chat";
                        iconType = 'avatar';
                        $( 'div.top-info div.room-indicator' ).addClass('hidden');
                    } else if (room.type == "dm") {
                        title = "Direct message";
                        iconType = 'avatar';
                        $( 'div.top-info div.room-indicator' ).addClass('hidden');
                    } else {
                        title = "Public room";
                        iconType = 'room';
                        $( 'div.top-info div.room-indicator' ).removeClass('hidden');
                    }
                    $( '#room-title' ).text(title);
                    if (room.type == 'chat') {
                        $( '#leave-type' ).text('leave chat');
                    } else if (room.type == 'dm') {
                        $( '#leave-type' ).text('close chat');
                    } else {
                        $( '#leave-type' ).text('leave room');
                    }

                    $( 'div.info div.title-wrapper' ).show();
                    $( 'div.info div.actions' ).show();
                    $( 'div.top-info div.icon' ).removeClass('room').removeClass('avatar').addClass(iconType);
                    $( 'div.top-info div.icon img' ).attr('src', room.icon);
                    $( 'div.top-info div.icon' ).removeClass('hidden');
                    $( 'div.top-info div.title' ).html(escapeHtml(room.name));
                    $( 'div.top-info div.topic' ).html(linkifyHtml(escapeHtml(room.topic), linkifyOptions));
                    $( '#leave-room' ).attr('roomid', roomid);
                    $( '#edit-info' ).attr('roomid', roomid);

                    updated = true;

                    this.roomType = room.type;
                    this.moderated = room.moderated;
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

    /**
     * Called internally when we need to update the information about the currently displayed room. This
     * is the DOM update function which keeps the various elements on-screen in sync with info we know about
     * the room.
     */
    _updateRoom( roomid ) {
        if (roomid == this.roomid && this.infoLoaded) {
            this.rooms.forEach((room) => {
                if (room.id == roomid) {
                    var title;
                    if (room.type == "chat") {
                        title = "Private chat";
                        $( 'div.top-info div.room-indicator' ).addClass('hidden');
                    } else if (room.type == "dm") {
                        title = "Direct message";
                        $( 'div.top-info div.room-indicator' ).addClass('hidden');
                    } else {
                        title = "Public room";
                        $( 'div.top-info div.room-indicator' ).removeClass('hidden');
                    }
                    $( '#room-title' ).text(title);
                    if (room.type == 'chat') {
                        $( '#leave-type' ).text('leave chat');
                    } else if (room.type == 'dm') {
                        $( '#leave-type' ).text('close chat');
                    } else {
                        $( '#leave-type' ).text('leave room');
                    }

                    $( 'div.top-info div.title' ).html(escapeHtml(room.name));
                    $( 'div.top-info div.topic' ).html(linkifyHtml(escapeHtml(room.topic), linkifyOptions));
                    $( 'div.top-info div.icon img' ).attr('src', room.icon);
                    this.chatdetails.setRoom(room);
                }
            });
        }
    }

    /**
     * Called whenever the manager informs us that we've left a room. This can happen when
     * the user chooses to leave a room via the info panel. There is not currently a method
     * for having the server kick a user from a room and update the client, but when that's
     * added the manager will call this function as well.
     */
    closeRoom( roomid ) {
        if (roomid == this.roomid) {
            this.chatdetails.closeRoom(roomid);
            this.occupants = [];
            this.occupantsLoaded = false;
            this.infoLoaded = false;
            this.roomid = "";
            this.roomType = "chat";
            this.moderated = false;

            $( 'div.info > div.occupants' ).empty();
            $( '#leave-room' ).attr('roomid', '');
            $( '#edit-info' ).attr('roomid', '');
            $( 'div.top-info div.title' ).html('&nbsp;');
            $( 'div.top-info div.topic' ).html('&nbsp;');
            $( 'div.top-info div.icon' ).addClass('hidden');
            $( 'div.info div.title-wrapper' ).hide();
            $( 'div.info div.actions' ).hide();
        }
    }
}

export { Info };
