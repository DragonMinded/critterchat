import $ from "jquery";
import { escapeHtml } from "./utils.js";
import { EditProfile } from "./modals/editprofile.js";
import { EditPreferences } from "./modals/editpreferences.js";
import { displayWarning } from "./modals/warningmodal.js";
import { Search } from "./modals/search.js";

/**
 * The class responsible for the left hand menu. This also generates room change request events
 * when the user clicks on a new room. It also handles tab notifications and favicon notifications
 * since it cares about notification badges on various rooms. Additionally, since various action
 * buttons are in the menu panel, this manages the search, edit profile and edit preferences popover
 * dialogs. Mostly it does that by ferrying various server information that was loaded and passed
 * to us onward to these components.
 */
class Menu {
    constructor( eventBus, screenState, inputState, initialSize, initialVisibility ) {
        this.eventBus = eventBus;
        this.screenState = screenState;
        this.inputState = inputState;
        this.editProfile = new EditProfile( eventBus, inputState );
        this.editPreferences = new EditPreferences( eventBus, inputState );
        this.search = new Search( eventBus, inputState )
        this.size = initialSize;
        this.visibility = initialVisibility;
        this.title = document.title;

        this.rooms = [];
        this.selected = "";
        this.pendingRoomSelect = "";
        this.lastSettings = {};
        this.roomsLoaded = false;
        this.lastSettingsLoaded = false;
        this.preferences = {}
        this.preferencesLoaded = false;

        // Handles figuring out if we need to put a title notification or badges up
        // on the various panes when the user is on mobile.
        this.chatVisible = true;

        $( 'div.menu > div.rooms' ).on( 'click', () => {
            this.inputState.setState("empty");
        });

        $( '#edit-profile' ).on( 'click', (event) => {
            event.preventDefault();

            this.inputState.setState("empty");
            this.editProfile.display();
        });

        $( '#edit-preferences' ).on( 'click', (event) => {
            event.preventDefault();

            this.inputState.setState("empty");
            this.editPreferences.display();
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
            this._updateSize();
            this._recalculateVisibility();
        });

        eventBus.on( 'updatevisibility', (newVisibility) => {
            this.visibility = newVisibility;
            this._recalculateVisibility();
        });

        this.screenState.registerStateChangeCallback(() => {
            this._updateSize();
            this._recalculateVisibility();
        });

        this._updateSize();
        this._recalculateVisibility();
    }

    /**
     * Determines whether the current room's chat pane is actually visible to the user. This is false
     * when the user is in a different tab (visibility is hidden) or when the user is on mobile and
     * not currently on the chat pane.
     */
    _recalculateVisibility() {
        if (this.visibility == "hidden") {
            this.chatVisible = false;
        } else if (this.size == "mobile" && this.screenState.current != "chat") {
            this.chatVisible = false;
        } else {
            this.chatVisible = true;
        }

        if (this.chatVisible) {
            if (this.selected) {
                this._clearBadges(this.selected);
            }
        }

        this._updateGlobalBadges();
    }

    /**
     * Called whenever the manager notifies us that our screen size has moved from desktop to mobile
     * or mobile to desktop. We use this to reflow whether we're pinned to the left side or possibly
     * displayed as a full-size panel.
     */
    _updateSize() {
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

    /**
     * Called whenever the manager informs us of an updated room list from the server. The room list
     * is always absolute and includes all relevant rooms that we're in, ordered by last update newest
     * to oldest. We use this to re-order rooms when necessary, as well as add new rooms to the list
     * if the user has joined a new room or started a new chat. If the last settings was loaded before
     * this is called, the last thing we will do is select that room.
     */
    setRooms( rooms, forceDraw ) {
        // First, sort rooms based on preferences.
        var sortedRooms = [];
        if (this.preferencesLoaded && this.preferences.rooms_on_top) {
            rooms.forEach((room) => {
                if (room.type == "room") {
                    sortedRooms.push(room);
                }
            });
            rooms.forEach((room) => {
                if (room.type == "chat" || room.type == "dm") {
                    sortedRooms.push(room);
                }
            });
        } else {
            sortedRooms = rooms;
        }

        // Redraw if the room length or ordering changed, otherwise refresh in place.
        var needsEmpty = false;
        if (forceDraw) {
            needsEmpty = true;
        } else {
            if (sortedRooms.length == this.rooms.length) {
                for (var i = 0; i < sortedRooms.length; i++) {
                    if (sortedRooms[i].id != this.rooms[i].id) {
                        needsEmpty = true;
                        break;
                    }
                }
            } else {
                needsEmpty = true;
            }
        }

        // Make sure to preserve badge counts since we're overwriting our rooms list.
        var counts = {};
        this.rooms.forEach((room) => {
            counts[room.id] = room.count || "";
        });

        // Make a copy instead of holding onto a reference, so we can mutate.
        this.rooms = rooms.filter(() => true);
        this.roomsLoaded = true;

        // Copy badge counts over to both our stored and rendered lists.
        this.rooms.forEach((room) => {
            room.count = counts[room.id];
        });
        sortedRooms.forEach((room) => {
            if (counts[room.id] != undefined) {
                room.count = counts[room.id];
            }
        });

        // If we re-arranged anything, nuke our existing.
        var scrollPos = $('div.menu > div.rooms').scrollTop();
        if (needsEmpty) {
            $('div.menu > div.rooms').empty();
        }

        // Draw the sorted order, and then select the room.
        sortedRooms.forEach((room) => this._drawRoom(room));
        $('div.menu > div.rooms').scrollTop(scrollPos);

        if (this.pendingRoomSelect) {
            this.selectRoom(this.pendingRoomSelect);
            this.pendingRoomSelect = "";
        }
    }

    /**
     * Called whenever settings are received from the server. This only happens upon a successful
     * connection and not any time after, so we use it to navigate to the last viewed room from before
     * we were closed and reopened or refreshed. In the case that rooms aren't loaded, we simply set
     * the settings and when the room list comes in we will navigate to the correct room at that time.
     */
    setLastSettings( settings ) {
        this.lastSettings = settings;
        this.lastSettingsLoaded = true;

        if (this.roomsLoaded) {
            this.selectRoom(this.lastSettings.roomid);
        } else {
            this.pendingRoomSelect = this.lastSettings.roomid;
        }
    }

    /**
     * Called every time the server informs us that our profile was updated, as well as once every
     * connection success or reconnect. We just use this to pass on the profile to the edit profile
     * popover that we manage.
     */
    setProfile( profile ) {
        this.editProfile.setProfile( profile );
    }

    /**
     * Called every time the server informs us that preferences were updated, as well as once every
     * connection success or reconnect. We use this to pass on preferences to the edit preferences
     * popover we manage, as well as update our title badge and room ordering, because both of those
     * are affected by preferences.
     */
    setPreferences( preferences ) {
        this.preferences = preferences;
        this.preferencesLoaded = true;
        this.editPreferences.setPreferences( preferences );
        this._updateGlobalBadges();
        if (this.roomsLoaded) {
            this.setRooms(this.rooms, true);
        }
    }

    /**
     * Called every time the server has updated search results which we pass onto the search instance
     * that we manage.
     */
    populateSearchResults( results ) {
        this.search.populateSearchResults( results );
    }

    /**
     * Given a room object, either add a DOM element representing that room in the right place in the
     * menu or update the existing DOM element that represents that room if it already exists.
     */
    _drawRoom( room ) {
        // First, see if this is an update.
        var conversations = $('div.menu > div.rooms');
        var drawnRoom = conversations.find('div.item#' + room.id);
        if (drawnRoom.length > 0) {
            drawnRoom.find('.icon img').attr('src', room.icon);
            drawnRoom.find('.name').html(escapeHtml(room.name));
        } else {
            // Now, draw it fresh since it's not an update.
            var type = room.type == 'room' ? 'room' : 'avatar';
            var html = '<div class="item" id="' + room.id + '">';
            html    += '  <div class="icon ' + type + '">';
            html    += '    <img src="' + room.icon + '" />';
            if (room.count) {
                html    += '    <div class="badge"><div class="count">' + room.count + '</div></div>';
            } else {
                html    += '    <div class="badge empty"><div class="count"></div></div>';
            }
            if (room.type == 'room') {
                html    += '    <div class="room-indicator">#</div>';
            }
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

        this._updateSelected();
    }

    /**
     * Called whenever the manager informs us that the server has requested we navigate to
     * a specific room. This is used to automatically jump to a given room when joining a new
     * room or starting a new chat. Additionally, called whenever the user clicks on a new room
     * or whenever we choose to select a room such as when we get our settings loaded.
     */
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
            this._updateSelected();
            this._clearBadges(roomid);

            this.eventBus.emit('selectroom', roomid);
        }

        if (found) {
            this.screenState.setState("chat");
        }

        if (this.size != "mobile") {
            $('input#message').focus();
        }
    }

    /**
     * Called whenever the manager informs us that we've left a room. This can happen when
     * the user chooses to leave a room via the info panel. There is not currently a method
     * for having the server kick a user from a room and update the client, but when that's
     * added the manager will call this function as well.
     */
    closeRoom( roomid ) {
        if (this.selected == roomid ) {
            this.selected = "";

            var conversations = $('div.menu > div.rooms');
            conversations.find('div.item#' + roomid).remove();

            this.rooms = this.rooms.filter((room) => room.id != roomid);

            this.screenState.setState("menu");
        }

        this._updateSelected();
    }

    /**
     * Manages the DOM to select the correct room and unselect the rest of the rooms. This
     * is tracked via a selected class which is also used for styling via CSS.
     */
    _updateSelected() {
        $('div.menu > div.rooms div.item').removeClass('selected');
        if (this.selected) {
            $('div.menu > div.rooms div.item#' + this.selected).addClass('selected');
        }
    }

    /**
     * Called whenever new actions are sent from the server to inform us that an action occurred.
     * We use this to track notification badges for rooms that we aren't in, as well as possibly
     * update the title notification if actions occur in the room we're in but we're backgrounded.
     */
    updateActions( roomid, actions ) {
        var count = 0;
        var notMeCount = 0;
        actions.forEach((action) => {
            if (
                action.action == "message" ||
                action.action == "join" ||
                action.action == "leave" ||
                action.action == "change_info"
            ) {
                count += 1;
                if (action.occupant.username != window.username) {
                    notMeCount += 1;
                }
            }
        });
        if (!this.chatVisible && roomid == this.selected) {
            this._updateBadges( roomid, notMeCount );
        } else if (roomid != this.selected) {
            this._updateBadges( roomid, count );
        }
        this._updateGlobalBadges();
    }

    /**
     * Given a specific room and a number of new actions that are relevant to that room, updates
     * the notification badge for that room to display the notification count. This is additive,
     * so if there's already a few notifications displayed and this adds a few more, the end result
     * will be the notification badge shows the sum of the new actions and existing actions.
     */
    _updateBadges( roomid, newactions ) {
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

    /**
     * Called whenever the server informs us of a new set of badge counts for a room. The
     * server can track the same badges as we can because the client sends last read notifications
     * to the server. This allows us to synchronize notification badge clears across multiple
     * devices and it is this function responsible for doing so.
     */
    setBadges( badges ) {
        if (this.roomsLoaded) {
            badges.forEach((obj) => {
                // Skip clearing the current room altogether if we're not viewing it.
                if (this.selected == obj.roomid && !this.chatvisible) {
                    return;
                }

                // Update with new server counts since another client could have read the chat.
                this._clearBadges(obj.roomid);
                if (obj.count) {
                    this._updateBadges(obj.roomid, obj.count);
                }
            });

            this._updateGlobalBadges();
        }
    }

    /**
     * Given a room ID, removes the notification badge from that room on the DOM.
     */
    _clearBadges( roomid ) {
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

        this._updateGlobalBadges();
    }

    /**
     * Manages determining whether the title should display a notification indicator or not
     * and updates the title in the DOM respectively. The logic for this includes whether the
     * uesr has configured title badge notification to be enabled, whether there are any
     * notifications for rooms not being viewed currently, and whether we have un read
     * notifications in the current channel (determined by checking whether we're a background
     * tab or not when new actions come in from the server). If the title badge is displayed
     * and we're in mobile, we also badge on the back buttons for various panes so a user who
     * is sitting on a chat or in the info pane can see that there are unread actions.
     */
    _updateGlobalBadges() {
        if (!this.roomsLoaded) {
            return;
        }

        // This will be true if there is a pending action anywhere in any of the rooms that
        // the user hasn't seen. This includes the current room if the tab is hidden or if
        // the user is on mobile and is not on the chat pane.
        var notified = false;
        var total = 0;
        this.rooms.forEach((room) => {
            if (room.count) {
                if (room.count == "!!") {
                    total += 10;
                } else {
                    total += parseInt(room.count);
                }
                notified = true;
            }
        });

        // Display notification count badges on various back buttons in mobile.
        if (total > 0) {
            $('div.back > div.badge').removeClass('empty');
            if (total > 9) {
                $('div.back > div.badge div.count').text('!!');
            } else {
                $('div.back > div.badge div.count').text(total);
            }
        } else {
            $('div.back > div.badge').addClass('empty');
            $('div.back > div.badge div.count').text("");
        }

        // Only show a title notification if the user asked us to do so.
        if (this.preferencesLoaded && this.preferences.title_notifs && notified) {
            document.title = "[\u2605] " + this.title;
        } else {
            document.title = this.title;
        }
    }
}

export { Menu };
