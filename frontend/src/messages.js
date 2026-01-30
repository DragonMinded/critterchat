import $ from "jquery";
import linkifyHtml from "linkify-html";

import {
    escapeHtml,
    formatDateTime,
    scrollTop,
    scrollTopMax,
    isInViewport,
    containsStandaloneText,
    highlightStandaloneText,
} from "./utils.js";
import { emojisearch } from "./components/emojisearch.js";
import { autocomplete } from "./components/autocomplete.js";
import { UploadPicker } from "./components/uploadpicker.js";
import { displayInfo } from "./modals/infomodal.js";

const linkifyOptions = { defaultProtocol: "http", target: "_blank", validate: { email: () => false } };

const searchOptions = {
    attributes: function( _icon, _variant ) {
        return {
            loading: "lazy",
            width: "72",
            height: "72",
        };
    },
};

/**
 * The class responsible for the chat pane in the center of the screen. This currently
 * means resonsiblity for rendering all of the incoming messages and other room actions,
 * as well as generating events for new messages being sent to a room. It is currently
 * in charge of the custom emotes for the system since it is currently the only component
 * that cares about looking them up for new messages.
 */
class Messages {
    constructor( eventBus, screenState, inputState, initialSize, initialVisibility ) {
        this.eventBus = eventBus;
        this.inputState = inputState;
        this.screenState = screenState;
        this.size = initialSize;
        this.visibility = initialVisibility;
        this.messages = [];
        this.occupants = [];
        this.rooms = new Map();
        this.pending = new Map();
        this.pendingroomid = "";
        this.roomid = "";
        this.roomType = "chat";
        this.autoscroll = true;
        this.lastAction = {};
        this.preferences = {};
        this.scrollTo = {};
        this.roomsLoaded = false;
        this.occupantsLoaded = false;

        // Handles making sure you can't mess with or double-post a message when one is sending.
        // We really should track this per-room, and also use it to block searching for emoji or
        // changing attachments, but this is better than nothing and prevents double-sending when
        // it appears that otherwise nothing is happening.
        this.pendingMessage = false;

        // Handles only updating the server with the last action if we're really viewing
        // the message.
        this.lastActionUpdate = {};
        this.lastActionPending = false;

        $( '#message-actions' ).on( 'submit', (event) => {
            event.preventDefault();

            this.inputState.setState("empty");
            var roomid = $( '#message-actions' ).attr('roomid');

            if (roomid) {
                // Grab message, focus on the message box if we clicked send.
                var message = $( 'input#message' ).val();
                $( 'input#message' ).focus();

                if (message && message.length > window.maxmessage) {
                    displayInfo(
                        'Your message is too long to be sent, please type fewer things!',
                        'okay!',
                    );
                } else {
                    // First, grab any attachments that should go with the message.
                    const files = this.uploadPicker.files( roomid );

                    if (message.length > 0 || files.length > 0) {
                        if (files.length > 0) {
                            // Prevent double-sending, especially with large attachments. We could do this for message
                            // only events, but that makes the send button annoyingly flash disabled for a split second.
                            // It's much more likely to double-send with attachments since they take awhile to upload.
                            this.pendingMessage = true;
                            $( 'button#sendmessage' ).prop('disabled', true);
                        }

                        // Now, send the event.
                        this.eventBus.emit(
                            'message',
                            {
                                'roomid': roomid,
                                'message': message,
                                'sensitive': $( 'div.message-visibility' ).hasClass('message-sensitive'),
                                'attachments': files,
                            },
                        );
                    }
                }
            }
        });

        $( 'div.chat > div.conversation-wrapper' ).on( 'click', () => {
            this.inputState.setState("empty");
        });

        $( 'div.chat > div.conversation-wrapper' ).scroll(() => {
            var box = $( 'div.chat > div.conversation-wrapper' );
            this.autoscroll = scrollTop(box[0]) >= (scrollTopMax(box[0]) - 5);
            if (this.autoscroll) {
                $( 'div.new-messages-alert' ).css( 'display', 'none' );
            }
        });

        $( document ).on( 'keydown', (evt) => {
            // Figure out if the user started typing, so we can redirect to the input control.
            const key = evt.key;
            const control = (key.length != 1) || (key == " ") || evt.ctrlKey || evt.metaKey || evt.altKey;
            const isBody = $(evt.target).is("body");
            const isPaste = (
                // Windows/linux paste.
                ((key == "v" || key == "V") && evt.ctrlKey) ||
                // Old style shift-insert paste.
                (key == "Insert" && evt.shiftKey) ||
                // OSX paste.
                ((key == "v" || key == "V") && evt.metaKey)
            );

            // Ignore events not to the global body.
            if (!isBody) {
                return;
            }
            // Ignore non-paste control and non-printable keys.
            if (control && !isPaste) {
                return;
            }

            // It is, and it's to the general body since no control is focused.
            $( 'input#message' ).focus();
        });

        $(window).resize(() => {
            var box = $( 'div.chat > div.conversation-wrapper' );
            if (this.autoscroll) {
                box[0].scrollTop = scrollTopMax(box[0]) + 1;
            }

            // Recalculate autoscroll since it could have been enabled by a resize.
            this.autoscroll = scrollTop(box[0]) >= (scrollTopMax(box[0]) - 5);
            if (this.autoscroll) {
                $( 'div.new-messages-alert' ).css( 'display', 'none' );
            }
        });

        $( 'div.chat > div.conversation-wrapper' ).scroll(() => {
            if (isInViewport($( ".scrolled-top.untriggered" ))) {
                this._loadOlderMessages();
            }
        });

        $( '#message' ).on('keydown', () => {
            // Let user press "ESC" on the main input box to close search box.
            if(this.inputState.current == "search") {
                this.inputState.setState("empty");
            }
        });

        $( 'div.attachment-picker' ).on( 'click', () => {
            if (this.roomid && this.rooms.has(this.roomid)) {
                this.uploadPicker.selectFiles(this.roomid, "image/*");
            }
        });

        $( 'div.message-visibility' ).on( 'click', () => {
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();

            if ($( 'div.message-visibility' ).hasClass('message-sensitive')) {
                $( 'div.message-visibility' ).addClass('message-visible').removeClass('message-sensitive');
            } else {
                $( 'div.message-visibility' ).addClass('message-sensitive').removeClass('message-visible');
            }
        });

        // Set up dynamic mobile detection.
        eventBus.on( 'resize', (newSize) => {
            this.size = newSize;
            this._updateSize();
            this._sendPendingUpdates();
        });

        eventBus.on( 'updatevisibility', (newVisibility) => {
            this.visibility = newVisibility;
            this._sendPendingUpdates();
        });

        // Ensure that showing/hiding info keeps us auto-scrolled.
        eventBus.on('updateinfo', (_info) => {
            this._ensureScrolled(false);
        });

        // Ensure we only clear user input on successful message acknowledgement.
        eventBus.on('messageack', (info) => {
            if (info.status == "success") {
                if (info.roomid == this.roomid) {
                    // Now reset the input.
                    $( 'input#message' ).val( '' );

                    // And allow input to take place.
                    this.pendingMessage = false;
                    $( 'button#sendmessage' ).prop('disabled', false);
                }

                // Always clear the attachment store for the room.
                this.pending.set(info.roomid, {"message": "", "sensitive": false});
                $( 'div.message-visibility' ).addClass('message-visible').removeClass('message-sensitive');
                this.uploadPicker.clearRoom( info.roomid );
            } else {
                // Just unblock the control to try again.
                this.pendingMessage = false;
                $( 'button#sendmessage' ).prop('disabled', false);
            }
        });

        // Ensure that we don't let any messages get sent during downtime.
        eventBus.on('connected', () => {
            if (!self.pendingMessage) {
                $( 'button#sendmessage' ).prop('disabled', false);
            }
        });
        eventBus.on('disconnected', () => {
            $( 'button#sendmessage' ).prop('disabled', true);
        });

        this.screenState.registerStateChangeCallback(() => {
            this._updateSize();
            this._sendPendingUpdates();
            this._ensureScrolled();
        });

        this._updateSize();

        // Set up the upload picker popover.
        this.uploadPicker = new UploadPicker( eventBus, screenState, '#message' );

        // Set up custom emotes, as well as normal emoji typeahead.
        this.autocompleteOptions = [];
        this.emojiSearchOptions = [];
        for (const [key, value] of Object.entries(window.emojis)) {
            this.autocompleteOptions.push(
                {text: key, type: "emoji", preview: twemoji.parse(value, twemojiOptions)}
            );
            this.emojiSearchOptions.push(
                {text: key, type: "emoji", preview: twemoji.parse(value, {...twemojiOptions, ...searchOptions})}
            );
        }
        for (const [key, value] of Object.entries(window.emotes)) {
            const src = "src=\"" + value.uri + "\"";
            const dims = "width=\"" + value.dimensions[0] + "\" height=\"" + value.dimensions[1] + "\"";

            this.autocompleteOptions.push(
                {text: key, type: "emote", preview: "<img class=\"emoji-preview\" " + src + " " + dims + " />"}
            );
            this.emojiSearchOptions.push(
                {text: key, type: "emote", preview: "<img class=\"emoji-preview\" " + src + " " + dims + " loading=\"lazy\" />"}
            );
        }
        this.emojisearchUpdate = emojisearch(this.inputState, '.emoji-search', '#message', this.emojiSearchOptions);

        // Support tab-completing users as well.
        this.autocompleteUpdate = autocomplete(this.inputState, '#message', this.autocompleteOptions);

        // Set up the emoji search itself.
        $(".emoji-search").html(twemoji.parse(String.fromCodePoint(0x1F600), twemojiOptions));

        // Ensure that the input box itself doesn't allow messages to be too long.
        $('#message').attr("maxlength", window.maxmessage);
    }

    /**
     * Called whenever chat messages become visible after being hidden, where we update the server with
     * last seen actions.
     */
    _sendPendingUpdates() {
        if (this.lastActionPending && this.visibility != "hidden" && !(this.size == "mobile" && this.screenState.current != "chat")) {
            this.eventBus.emit("lastaction", this.lastActionUpdate);
            this.lastActionPending = false;
        }
    }

    /**
     * Called whenever the manager notifies us that our screen size has moved from desktop to mobile
     * or mobile to desktop. We use this to decide whether we're displayed in the center of the screen
     * or as a full-size panel that gets displayed when a user clicks into a room from the menu.
     */
    _updateSize() {
        if (this.size == "mobile") {
            if (this.screenState.current == "chat") {
                $( 'div.container > div.chat' ).removeClass('hidden');
            } else {
                $( 'div.container > div.chat' ).addClass('hidden');
            }
        } else {
            $( 'div.container > div.chat' ).removeClass('hidden');
        }
    }

    /**
     * Used for tracking which action was truly the last action received. We determine this by
     * the order attribute present on all actions. The only guarantee the server gives us is that
     * newer actions will have a higher number than older actions, so we use that here.
     */
    _updateLastAction( action ) {
        if (!this.lastAction?.order) {
            this.lastAction = action;
        } else {
            if (action.order > this.lastAction.order) {
                this.lastAction = action;
            }
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
     * connection success or reconnect. We use this to potentially reflow the message page if the
     * user has toggled their combined messages preference.
     */
    setPreferences( preferences ) {
        this.preferences = preferences;
        this._combineMessages(true);
        this.uploadPicker.resizeRooms();
    }

    /**
     * Called whenever settings are received from the server. We don't care about this event but
     * a handler was placed here for consistency across top-level components.
     */
    setLastSettings( _settings ) {
        // This page intentionally left blank.
    }

    /**
     * Called wnever the manager informs us of room occupants for a given room. We only care about
     * occupants for the room we're in, so ignore any out-of-date notifications for rooms we have
     * clicked away from. We use this to keep our mentioning auto-complete up to date, so users
     * can select from an auto-complete popover when mentioning another user.
     */
    setOccupants( roomid, occupants ) {
        if (roomid == this.roomid) {
            this.occupants = occupants.filter((occupant) => !occupant.inactive);
            this.occupants.sort((a, b) => { return a.username.localeCompare(b.username); });
            this.occupantsLoaded = true;
            this._updateUsers();
        }
    }

    /**
     * Called whenever the manager informs us of an updated room list from the server. The room list
     * is always absolute and includes all relevant rooms that we're in, ordered by last update newest
     * to oldest. We only really care about the room list so we can track info about the currently
     * viewed room. If there was a pending room switch and we hadn't yet loaded rooms, this will
     * trigger that room switch upon loading.
     */
    setRooms( rooms ) {
        // Make a copy instead of keeping a reference, so we can safely mutate.
        const newRooms = new Map();
        rooms.forEach((room) => {
            newRooms.set(room.id, room);
        });

        this.rooms = newRooms;
        this.roomsLoaded = true;

        if (this.pendingroomid) {
            this.setRoom(this.pendingroomid);
        }
    }

    /**
     * Called when the manager informs us that the user has selected a new room, or when a new
     * room has been selected for the user (such as selecting a room after joining it). In either
     * case, we use this as an opportunity to wipe out the existing messages from the old room
     * in preparation for new history to arrive. Note that the manager is in charge of requesting
     * chat history for us when a new room is selected, so all we need to do is wait for that to
     * happen.
     */
    setRoom( roomid ) {
        if (this.roomsLoaded) {
            this.pendingroomid = "";
            if (roomid != this.roomid) {
                // First, save any old room message.
                if (this.roomid) {
                    this.pending.set(
                        this.roomid,
                        {
                            "message": $( 'input#message' ).val(),
                            "sensitive": $( 'div.message-visibility' ).hasClass('message-sensitive'),
                        },
                    );
                    this.uploadPicker.hideRoom( this.roomid );
                }

                // Now, show new room's message.
                if (this.pending.has(roomid)) {
                    $( 'input#message' ).val(this.pending.get(roomid).message);
                    if ( this.pending.get(roomid).sensitive ) {
                        $( 'div.message-visibility' ).addClass('message-sensitive').removeClass('message-visible');
                    } else {
                        $( 'div.message-visibility' ).addClass('message-visible').removeClass('message-sensitive');
                    }
                } else {
                    $( 'input#message' ).val('');
                    $( 'div.message-visibility' ).addClass('message-visible').removeClass('message-sensitive');
                }
                this.uploadPicker.showRoom( roomid );

                // Now, unblock any pending message block.
                this.pendingMessage = false;
                $( 'button#sendmessage' ).prop('disabled', false);

                // Now, swap to that room.
                if (this.rooms.has(roomid)) {
                    this.messages = [];
                    this.roomid = roomid;
                    this.lastAction = {};
                    this.autoscroll = true;
                    this.occupants = [];
                    this.occupantsLoaded = false;
                    this.lastActionPending = false;
                    this.roomType = this.rooms.get(roomid).type;
                    this._updateUsers();

                    $('div.chat > div.conversation-wrapper > div.conversation').empty();
                    $( '#message-actions' ).attr('roomid', roomid);
                }
            }
        } else {
            this.pendingroomid = roomid;
        }
    }

    /**
     * Called whenever the manager informs us that we've left a room. This can happen when
     * the user chooses to leave a room via the info panel. There is not currently a method
     * for having the server kick a user from a room and update the client, but when that's
     * added the manager will call this function as well.
     */
    closeRoom( roomid ) {
        // Nuke pending message since we're closing the room.
        this.pending.set(roomid, {'message': '', 'sensitive': false});
        $( 'div.message-visibility' ).addClass('message-visible').removeClass('message-sensitive');

        this.uploadPicker.hideRoom( roomid );

        if (roomid == this.roomid) {
            this.message = [];
            this.roomid = "";
            this.lastAction = {};
            this.autoscroll = true;
            this.occupants = [];
            this.occupantsLoaded = false;
            this.lastActionPending = false;
            this._updateUsers();

            $('div.chat > div.conversation-wrapper > div.conversation').empty();
            $( '#message-actions' ).attr('roomid', '');
        }
    }

    /**
     * Used by various components to ensure that if the user was scrolled to the bottom of
     * the message container, they remain there. This is how we implement auto-scrolling
     * upon receipt of new messages. If the user is scrolled up, this also managed adding
     * the new message indicator, but only if this was called as a result of a new action
     * being added. In some cases, when we reflow the chat (such as swapping combined
     * messages on or off) we only want to ensure scrolled if appropriate, but don't want
     * to erroneously display a new messages indicator if the user was scrolled up.
     */
    _ensureScrolled( causedByNewMessage ) {
        var box = $( 'div.chat > div.conversation-wrapper' );
        if (this.autoscroll) {
            box[0].scrollTop = scrollTopMax(box[0]) + 1;
        } else {
            // We don't want to display the alert in this case, possibly because we
            // were not drawing new messages but instead trying to auto-scroll after
            // a re-flow.
            if (causedByNewMessage) {
                $( 'div.new-messages-alert' ).css( 'display', 'inline-block' );
            }
        }
    }

    /**
     * Called when the server loads the history for this room. This happens either when
     * switching to a new room after we've blanked the messages, or when we scroll to the
     * top of the message window and request the server to load older messages. In both
     * cases, we ignore updates for rooms we are no longer in and then draw the messages,
     * finally updating the new message indicator based on our last seen message.
     */
    updateHistory( roomid, history, lastSeen ) {
        if (roomid != this.roomid) {
            // Must be an out of date lookup, ignore it.
            return;
        }

        this._drawActions( history );

        if ( lastSeen ) {
            this._addNewIndicator( lastSeen );
        }
    }

    /**
     * Simply returns true if there is a new messages indicator somewhere in the chat panel,
     * and false otherwise. Note that this is the horizontal rule that denotes messages above
     * are old and messages below are new, as determined by the last seen message ID.
     */
    _isNewIndicatorPresent() {
        return $('div.newseparator').length > 0;
    }

    /**
     * Given a last seen message ID, ensures that a new indicator horizontal rule is added
     * to the DOM below that message. If an existing indicator is present, moves to the new
     * location. Otherwise, adds a new one in the right spot.
     */
    _addNewIndicator( lastSeen ) {
        // First, find the message this is referring to.
        var lastMessage = null;
        this.messages.forEach((message) => {
            if (message.id == lastSeen) {
                lastMessage = message;
            }
        });

        if (!lastMessage) {
            return;
        }

        // Now, grab all messages that are newer than this.
        var newerMessages = 0;
        this.messages.forEach((message) => {
            if (message.order > lastMessage.order) {
                if (
                    message.action == "message" ||
                    message.action == "join" ||
                    message.action == "leave" ||
                    message.action == "change_info"
                ) {
                    newerMessages += 1;
                }
            }
        });

        if (newerMessages) {
            var html = "";

            html  = '<div class="newseparator">';
            html += '  <div class="content-wrapper">';
            html += '    <div class="newline">&nbsp;</div>';
            html += '    <div class="newmessage">new</div>';
            html += '    <div class="newline">&nbsp;</div>';
            html += '  </div>';
            html += '</div>';

            var messages = $('div.chat > div.conversation-wrapper > div.conversation');

            this._removeNewIndicator();
            $(html).insertAfter(messages.find('div.item#' + lastMessage.id));

            this._ensureScrolled(true);
        }
    }

    /**
     * Simply removes any new indicator horizontal rule anywhere on the chat panel.
     */
    _removeNewIndicator() {
        $('div.newseparator').remove();
        this._ensureScrolled(true);
    }

    /**
     * Called whenever new actions are sent from the server to inform us that an action occurred.
     * We use this not only to keep our user list in sync after receiving the list from the rooms
     * response handled in setRooms(), but also to display new messages as they come in from other
     * chatters, and to determine when to clear the new message indicator that might be on the
     * screen. The latter we clear only when the user sends a message to the channel or tabs out
     * to another room and back in.
     */
    updateActions( roomid, actions ) {
        if (roomid != this.roomid) {
            // Must be an out of date lookup, ignore it.
            return;
        }

        // If this action is not visible, calculate the last seen message so we can add the new message indicator
        // to the current page.
        const lastSeenMessage = (this.visibility == "hidden" || !this.autoscroll) ? this._getLatestMessage() : undefined;

        var changed = false;
        var selfMessage = false;
        if (this.occupantsLoaded) {
            actions.forEach((message) => {
                // This is where we get notified of user joins and leaves.
                if (message.action == "join") {
                    // Add a new occupant to our list.
                    this.occupants.push(message.occupant);
                    changed = true;
                } else if (message.action == "leave") {
                    this.occupants = this.occupants.filter((occupant) => occupant.id != message.occupant.id);
                    changed = true;
                }

                // Remove -- new -- indicator on receipt of own message instead of on send, since
                // it can take a little while to round trip and the double change to the message
                // window looks weird.
                if (message.occupant.username == window.username) {
                    if (
                        message.action == "message" ||
                        message.action == "change_info"
                    ) {
                        selfMessage = true;
                    }
                }
            });
        }

        if (changed) {
            this.occupants.sort((a, b) => { return a.username.localeCompare(b.username); });
            this._updateUsers();
        }

        this._drawActions( actions );

        if (this.visibility == "hidden" && lastSeenMessage && !this._isNewIndicatorPresent()) {
            // Add a new messages line if we're in another tab, so we can tab back to new messages.
            this._addNewIndicator( lastSeenMessage.id );
        } else if (!this.autoscroll && lastSeenMessage && !this._isNewIndicatorPresent()) {
            // Add a new messgaes line if we're scrolled up, so we can scroll down to new messages.
            this._addNewIndicator( lastSeenMessage.id );
        } else if (selfMessage) {
            // We messaged this channel so nothing is new, we've seen it all.
            this._removeNewIndicator();
        }
    }

    /**
     * Draws the older messages available indicator to the top of the messages panel which when
     * scrolled to will trigger us to fetch the next oldest messages to display to the user.
     * Note that if there are no additional messages to display, this will skip drawing the
     * loader entirely.
     */
    _drawOlderMessagesLoader() {
        // Remove any scroll detectors and add a new one at the top.
        $( '.scrolled-top' ).remove();

        if (this.roomid && this.rooms.has(this.roomid)) {
            const lowestMessage = this._getEarliestMessage();
            const room = this.rooms.get(this.roomid);

            if (room.oldest_action && lowestMessage && room.oldest_action != lowestMessage.id) {
                $('div.chat > div.conversation-wrapper > div.conversation').prepend('<div class="scrolled-top untriggered">...</div>');
            }
        }
    }

    /**
     * Function that is called when the older messages available indicator is scrolled into view.
     * We use this to trigger a request to the manager to grab the next oldest message chunk so
     * we can render those as older message history.
     */
    _loadOlderMessages() {
        var lowestMessage = this._getEarliestMessage();
        if (lowestMessage) {
            const messages = $('div.chat > div.conversation-wrapper > div.conversation > div.item');
            const oldest = messages.first();

            if (messages && oldest) {
                this.scrollTo = {id: oldest.attr('id'), position: oldest.position().top};
            }

            $( '.scrolled-top' ).removeClass('untriggered');

            this.eventBus.emit("loadhistory", {"roomid": this.roomid, "before": lowestMessage.id})
        }
    }

    /**
     * Ensures that we have scrolled to a particular message, trying to keep that message in
     * the same spot vertically as it was before. We use this to make sure that the view jumps
     * as minimally as possible when loading older messages after the user scrolls up to the
     * top of the existing message list.
     */
    _scrollToMessage() {
        if (this.scrollTo.id) {
            const item = $('div.chat > div.conversation-wrapper > div.conversation > div.item#' + this.scrollTo.id);
            if (item && item.position()) {
                const delta = item.position().top - this.scrollTo.position;
                if (delta) {
                    var box = $( 'div.chat > div.conversation-wrapper' );
                    box[0].scrollTop = box[0].scrollTop + delta;
                }
            }

            this.scrollTo = {};
        }
    }

    /**
     * Gets the actual action object for the earliest message received in the chat, defined
     * as the action with the lowest order attribute.
     */
    _getEarliestMessage() {
        var lowestMessage = undefined;
        for (const message of this.messages) {
            if (lowestMessage == undefined) {
                lowestMessage = message;
            } else {
                if (message.order < lowestMessage.order) {
                    lowestMessage = message;
                }
            }
        }
        return lowestMessage;
    }

    /**
     * Gets the oldest message and returns the order attribute for it. If there is no earliest
     * message this will instead return -1.
     */
    _getEarliestMessageOrder() {
        var lowestMessage = this._getEarliestMessage();
        return lowestMessage ? lowestMessage.order : -1;
    }

    /**
     * Gets the actual action object for the latest message received in the chat, defined
     * as the action with the highest order attribute.
     */
    _getLatestMessage() {
        var highestMessage = undefined;
        for (const message of this.messages) {
            if (highestMessage == undefined) {
                highestMessage = message;
            } else {
                if (message.order > highestMessage.order) {
                    highestMessage = message;
                }
            }
        }
        return highestMessage;
    }

    /**
     * Gets the latest message and returns the order attribute for it. If there is no latest
     * message this will instead return -1.
     */
    _getLatestMessageOrder() {
        var highestMessage = this._getLatestMessage();
        return highestMessage ? highestMessage.order : -1;
    }

    /**
     * The function responsible for rendering individual actions to the screen as DOM elements.
     * This will order messages based on whether they should be grafted before the existing
     * messages (old history load) or after existing messages (new actions sent since loading
     * into the room). It is also responsible for tracking the last seen message, since you
     * sort of have to render a message to see it.
     */
    _drawActions( history ) {
        var lowestorder = this._getEarliestMessageOrder();
        var prepend = [];
        var append = [];
        if (lowestorder == -1) {
            // Just put all of the messages in after.
            append.push.apply(append, history);
        } else {
            // Sort into messages that are before or after the first message.
            for (const message of history) {
                if (message.order < lowestorder) {
                    prepend.push(message);
                } else {
                    append.push(message);
                }
            }
        }

        this.messages.push.apply(this.messages, history);

        prepend.sort((a, b) => b.order - a.order);
        append.sort((a, b) => a.order - b.order);

        var oldactionid = this.lastAction?.id;

        prepend.forEach((message) => this._drawMessage(message, 'before'));
        append.forEach((message) => this._drawMessage(message, 'after'));

        this._combineMessages(false);
        this._drawOlderMessagesLoader();
        this._scrollToMessage();

        if (this.lastAction.id != oldactionid) {
            const update = {"roomid": this.roomid, "actionid": this.lastAction.id};
            if (this.visibility == "hidden" || (this.size == "mobile" && this.screenState.current != "chat")) {
                this.lastActionUpdate = update;
                this.lastActionPending = true;
            } else {
                this.eventBus.emit("lastaction", update);
                this.lastActionPending = false;
            }
        }
    }

    /**
     * Whenever user changes occur (joins/parts/renames), update the autocomplete typeahead for those names.
     */
    _updateUsers() {
        var acusers = this.occupants.map(function(user) {
            return {
                text: "@" + user.username,
                type: "user",
                preview: "<img class=\"icon-preview\" src=\"" + user.icon + "\" />&nbsp;<span dir=\"auto\">" + escapeHtml(user.nickname) + "</span>",
            };
        });
        this.autocompleteUpdate(this.autocompleteOptions.concat(acusers));
    }

    /**
     * Called whenever the manager is notified of new custom emotes that were added to the server. Whenever
     * an emote is live-added, update the autocomplete typeahead and emoji search popover for that emote.
     */
    addEmotes( mapping ) {
        for (const [alias, details] of Object.entries(mapping)) {
            window.emotes[alias] = details;
            const src = "src=\"" + details.uri + "\"";
            const dims = "width=\"" + details.dimensions[0] + "\" height=\"" + details.dimensions[1] + "\"";

            this.autocompleteOptions.push(
                {text: alias, type: "emote", preview: "<img class=\"emoji-preview\" " + src + " " + dims + " />"}
            );
            this.emojiSearchOptions.push(
                {text: alias, type: "emote", preview: "<img class=\"emoji-preview\" " + src + " " + dims + " loading=\"lazy\" />"}
            );
        }

        this.emojisearchUpdate(this.emojiSearchOptions);
        this._updateUsers();
    }

    /**
     * Called whenever the manager is notified of custom emotes that were removed from the server. Whenever
     * an emote is live-removed, update the autocomplete typeahead and emoji search popover to remove that
     * emote.
     */
    deleteEmotes( aliases ) {
        aliases.forEach((alias) => {
            delete emotes[alias];
            this.autocompleteOptions = this.autocompleteOptions.filter((option) => !(option.type == "emote" && option.text == alias));
            this.emojiSearchOptions = this.emojiSearchOptions.filter((option) => !(option.type == "emote" && option.text == alias));
        });
        this.emojisearchUpdate(this.emojiSearchOptions);
        this._updateUsers();
    }

    /**
     * Returns image dimensions, capped to a given maximum height, respecting aspect ratios.
     */
    _getDims( attachment, desiredHeight ) {
        var width = attachment.metadata.width;
        var height = attachment.metadata.height;

        if (height > desiredHeight) {
            width = Math.round((width * desiredHeight) / height);
            height = desiredHeight;
        }

        return ' width="' + width + '" height="' + height + '" ';
    }

    /**
     * The actual function that handles DOM manipulation for rendering a new or updated action.
     * Note that right now while the server CAN send us old actions that have been edited in some
     * manner, it currently does not. However, this function handles that and will continue to be
     * the place where actions are updated after displaying if they are edited or reactions are
     * added.
     */
    _drawMessage( message, loc ) {
        // First, see if this is an update.
        var messages = $('div.chat > div.conversation-wrapper > div.conversation');
        var drawnMessage = messages.find('div.message#' + message.id);
        if (drawnMessage.length > 0) {
            if (message.action == "message") {
                let content = this._formatMessage(message.details.message);
                let highlighted = this._wasHighlighted(message.details.message);
                drawnMessage.html(content);

                if (highlighted) {
                    drawnMessage.addClass("highlighted");
                } else {
                    drawnMessage.removeClass("highlighted");
                }
            }
        } else {
            // Now, draw it fresh since it's not an update.
            var html = "";
            if (message.action == "message") {
                let content = this._formatMessage(message.details.message);
                let highlighted = this._wasHighlighted(message.details.message);

                html  = '<div class="item" id="' + message.id + '">';
                html += '  <div class="icon avatar" id="' + message.occupant.id + '">';
                html += '    <img src="' + message.occupant.icon + '" />';
                html += '  </div>';
                html += '  <div class="content-wrapper">';
                html += '    <div class="meta-wrapper">';
                html += '      <span class="name" dir="auto" id="' + message.occupant.id + '">' + escapeHtml(message.occupant.nickname) + '</span>';
                html += '      <span class="timestamp">' + formatDateTime(message.timestamp) + '</span>';
                html += '    </div>';
                html += '    <div class="message' + (highlighted ? " highlighted" : "") + (message.details.sensitive ? " sensitive" : "") + '" dir="auto" id="' + message.id + '">' + content + '</div>';

                if (message.attachments.length) {
                    const desiredHeight = message.attachments.length == 1 ? 300 : 100;

                    html += '    <div class="attachments">';
                    message.attachments.forEach((attachment) => {
                        var attachImg = $(
                            '<img src="' + attachment.uri + '"' + this._getDims(attachment, desiredHeight) + '/>'
                        ).attr('alt', attachment.metadata.alt_text || "message attachment");

                        if (attachment.metadata.sensitive) {
                            attachImg = attachImg.addClass('blurred');
                        }

                        if (attachment.metadata.alt_text) {
                            attachImg = attachImg.attr('title', attachment.metadata.alt_text);
                        }

                        html += '      <a target="_blank" href="' + attachment.uri + '">';
                        html += '        ' + attachImg.prop('outerHTML');

                        if (attachment.metadata.sensitive) {
                            html += '        <div class="blurred"><div class="maskable attachment-sensitive"></div></div>';
                        }

                        html += '      </a>';
                    });
                    html += '    </div>';
                }
                html += '  </div>';
                html += '</div>';
            } else if (message.action == "join") {
                html  = '<div class="item" id="' + message.id + '">';
                html += '  <div class="content-wrapper">';
                html += '    <div class="meta-wrapper">';
                html += '      <div class="action-wrapper">';
                html += '        <span class="name" dir="auto" id="' + message.occupant.id + '">' + escapeHtml(message.occupant.nickname) + '</span>';
                html += '        <span class="action">has joined!</span>';
                html += '      </div>';
                html += '      <span class="timestamp">' + formatDateTime(message.timestamp) + '</span>';
                html += '    </div>';
                html += '  </div>';
                html += '</div>';
            } else if (message.action == "leave") {
                html  = '<div class="item" id="' + message.id + '">';
                html += '  <div class="content-wrapper">';
                html += '    <div class="meta-wrapper">';
                html += '      <div class="action-wrapper">';
                html += '        <span class="name" dir="auto" id="' + message.occupant.id + '">' + escapeHtml(message.occupant.nickname) + '</span>';
                html += '        <span class="action">has left!</span>';
                html += '      </div>';
                html += '      <span class="timestamp">' + formatDateTime(message.timestamp) + '</span>';
                html += '    </div>';
                html += '  </div>';
                html += '</div>';
            } else if (message.action == "change_info") {
                var type = this.roomType == "chat" ? "chat" : "room";

                html  = '<div class="item" id="' + message.id + '">';
                html += '  <div class="content-wrapper">';
                html += '    <div class="meta-wrapper">';
                html += '      <div class="action-wrapper">';
                html += '        <span class="name" dir="auto" id="' + message.occupant.id + '">' + escapeHtml(message.occupant.nickname) + '</span>';
                html += '        <span class="action">has updated the ' + type + '\'s info!</span>';
                html += '      </div>';
                html += '      <span class="timestamp">' + formatDateTime(message.timestamp) + '</span>';
                html += '    </div>';
                html += '  </div>';
                html += '</div>';
            } else if (message.action == "change_profile") {
                // Just update the name and icon since this is a change.
                $('div.chat > div.conversation-wrapper > div.conversation span.name#' + message.occupant.id).html(escapeHtml(message.occupant.nickname));
                $('div.chat > div.conversation-wrapper > div.conversation div.icon#' + message.occupant.id + ' img').attr('src', message.occupant.icon);
            }

            // Place either before or after existing messages depending on if it's a backfill or a new message.
            if (html) {
                if (loc == 'after') {
                    messages.append(html);
                    this._ensureScrolled(true);
                } else {
                    messages.prepend(html);
                }
            }

            // Allow clicking a username in a message to view the person's profile.
            $('div.item#' + message.id + ' span.name#' + message.occupant.id).on('click', (event) => {
                event.stopPropagation();
                event.stopImmediatePropagation();

                this.inputState.setState("empty");

                var id = $(event.currentTarget).attr('id')
                this.eventBus.emit('displayprofile', id);
            });

            // Allow clicking on a username in the message itself.
            $('div.item#' + message.id + ' span.name-link').on('click', (event) => {
                event.stopPropagation();
                event.stopImmediatePropagation();

                var id = $(event.currentTarget).attr('id')
                this.eventBus.emit('displayprofile', id);
            });

            // Allow un-spoilering sensitive messages.
            $('div.message.sensitive').on('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();

                const elem = $(event.currentTarget);
                elem.removeClass('sensitive');
                elem.off();
            });
            $('div.attachments div.blurred').on('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();

                const elem = $(event.currentTarget);
                elem.parent().find('img.blurred').removeClass('blurred');
                elem.remove();
            });
        }

        this._updateLastAction(message);
    }

    /**
     * Function responsible for ensuring that messages which should be combined into the previous
     * message have the correct CSS classes so that styling can be applied to combine the message
     * with the previous. Note that this always does a complete reflow when called. The reason
     * for this is because it's possible that we would have made a different combining decision
     * with some messages that were older than what we currently have, and when loading those old
     * messages we need to reflow the combination logic to handle that. Note that this is also
     * called when the user toggles the preference for combining messages on or off. Since it
     * always reflows the whole container this is how we can achieve live re-display when the
     * preference is toggled.
     */
    _combineMessages( reflow ) {
        var messages = $('div.chat > div.conversation-wrapper > div.conversation');

        if (this.preferences.combined_messages) {
            // Go through and update our combined messages because we either got a new
            // message or the preference was toggled.
            var lastOccupant = undefined;
            var firstTimestamp = 0;
            var combined = 0;

            var indexedMessages = new Map();
            this.messages.forEach((msg) => {
                indexedMessages.set(msg.id, msg);
            });

            messages.find('div.item').each((_idx, elem) => {
                const msg = indexedMessages.get($(elem).attr('id'));
                const occupant = msg.occupant.id;
                const timestamp = msg.timestamp;

                // First, non-messages always break the chain.
                if (msg.action != "message") {
                    // This is a join/part/change info/etc, reset our combining.
                    lastOccupant = undefined;
                    firstTimestamp = 0;
                    combined = 0;
                }
                // Now, if it's a message by a different occupant, reset our combining.
                else if (lastOccupant != occupant) {
                    lastOccupant = occupant;
                    firstTimestamp = timestamp;
                    combined = 1;
                }
                // Next, if the timestamp is more than 5 minutes later than the first combined
                // message, split out to a new message.
                else if (timestamp >= (firstTimestamp + (5 * 60))) {
                    firstTimestamp = timestamp;
                    combined = 1;
                }
                // Next, if we've combined more than 10 messages in a row, split out to a new
                // message.
                else if (combined >= 10) {
                    firstTimestamp = timestamp;
                    combined = 1;
                }
                // Finally, this message can be combined!
                else {
                    combined += 1;
                    $(elem).addClass('combined');
                }
            });
        } else {
            // Go through and remove the combined messages class across the board because
            // we do not want to combine messages.
            messages.find('div.item').removeClass('combined');
        }

        if (reflow) {
            this._ensureScrolled(false);
        }
    }

    /**
     * Given a user-generated message, makes sure any HTML characters are escaped, highlights the user
     * if they were mentioned, formats the message as larger graphics if it contains only emoji, and
     * converts and links found in the message to clickable DOM elements.
     */
    _formatMessage( message ) {
        if (message.includes("@")) {
            return linkifyHtml(this._embiggen(this._clickulate(this._highlight(escapeHtml(message)))), linkifyOptions);
        } else {
            return linkifyHtml(this._embiggen(escapeHtml(message)), linkifyOptions);
        }
    }

    /**
     * Walks an already HTML-stripped and emojified message to see if any part of it is a reference
     * to the current user. If so, wraps that chunk of text in a highlight div, but does not change
     * capitalization. This allows your own name to be highlighted without rewriting how somebody
     * wrote the message.
     */
    _highlight( msg ) {
        var actualuser = '@' + window.username;
        var before = '<span class="name-highlight">';
        var after = '</span>';

        return highlightStandaloneText( msg, actualuser, before, after );
    }

    /**
     * Walks an already HTML-stripped and emojified message to make all usernames found in that message
     * clickable to go to the user's profile. Note that this works alongside the highlight above for
     * self-highlighting messages.
     */
    _clickulate( msg ) {
        if (!this.occupantsLoaded) {
            return msg;
        }

        this.occupants.forEach((occupant) => {
            var user = '@' + occupant.username;
            var before = '<span class="name-link" id="' + occupant.id + '">';
            var after = '</span>';

            msg = highlightStandaloneText( msg, user, before, after );
        });

        return msg;
    }

    /**
     * Return true if the raw text of a message sent by a user contains the current user's username
     * with a @ prefix (a mention) or false otherwise.
     */
    _wasHighlighted( message ) {
        const escaped = escapeHtml(message);
        const actualuser = '@' + window.username;
        return containsStandaloneText(escaped, actualuser);
    }

    /**
     * Takes an already HTML-stripped and emojified message and figures out if it contains only
     * emoji/emotes. If so, it makes them bigger because bigger emoji is more fun.
     */
    _embiggen( msg ) {
        if( msg.length == 0 ) {
            return msg;
        }

        var domentry = $('<span class="wrapperelement">' + msg + '</span>');
        var text = domentry.text().trim();
        var variationCount = 0;
        for (var i = 0; i < text.length; i++) {
            var code = text.charCodeAt(i);
            if (code >= 0xFE00 && code <= 0xFE0F) {
                variationCount ++;
            }
        }
        if ((text.length - variationCount) == 0 && msg.length > 0) {
            // Emoji only, embiggen the pictures.
            domentry.find('.emoji').addClass('emoji-big').removeClass('emoji');
            domentry.find('.emote').addClass('emote-big').removeClass('emote');
            return domentry.html();
        }

        return msg;
    }
}

export { Messages };
