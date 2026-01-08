import $ from "jquery";
import linkifyHtml from "linkify-html";

import {
    escapeHtml,
    formatDateTime,
    scrollTop,
    scrollTopMax,
    isInViewport,
    getSelectionText,
    containsStandaloneText,
} from "./utils.js";
import { emojisearch } from "./components/emojisearch.js";
import { autocomplete } from "./components/autocomplete.js";
import { displayInfo } from "./modals/infomodal.js";

const linkifyOptions = { defaultProtocol: "http", target: "_blank", validate: { email: () => false } };

const searchOptions = {
    attributes: function( _icon, _variant ) {
        return {
            loading: "lazy",
        }
    }
}

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
        this.pendingroomid = "";
        this.roomid = "";
        this.roomType = "chat";
        this.autoscroll = true;
        this.lastAction = {};
        this.preferences = {};
        this.scrollTo = {};
        this.roomsLoaded = false;
        this.occupantsLoaded = false;

        $( '#message-actions' ).on( 'submit', (event) => {
            event.preventDefault();

            this.inputState.setState("empty");
            var roomid = $( '#message-actions' ).attr('roomid');

            if (roomid) {
                var message = $( 'input#message' ).val();

                if (message && message.length > 64000) {
                    displayInfo(
                        'Your message is too long to be sent, please type fewer things!',
                        'okay!',
                    );
                } else {
                    $( 'input#message' ).val( '' );

                    if (message) {
                        this.eventBus.emit('message', {'roomid': roomid, 'message': message});
                    }
                }
            }
        });

        $( 'div.chat > div.conversation-wrapper' ).on( 'click', () => {
            this.inputState.setState("empty");

            if (!getSelectionText() && this.size != "mobile") {
                $('input#message').focus();
            }
        });

        $( 'div.chat > div.conversation-wrapper' ).scroll(() => {
            var box = $( 'div.chat > div.conversation-wrapper' );
            this.autoscroll = scrollTop(box[0]) >= (scrollTopMax(box[0]) - 5);
            if (this.autoscroll) {
                $( 'div.new-messages-alert' ).css( 'display', 'none' );
            }
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
                this.loadOlderMessages();
            }
        });

        $( '#message' ).on('keydown', () => {
            // Let user press "ESC" on the main input box to close search box.
            if(this.inputState.current == "search") {
                this.inputState.setState("empty");
            }
        });

        // Set up dynamic mobile detection.
        eventBus.on( 'resize', (newSize) => {
            this.size = newSize;
            this.updateSize();
        });

        eventBus.on( 'updatevisibility', (newVisibility) => {
            this.visibility = newVisibility;
        });

        // Ensure that showing/hiding info keeps us auto-scrolled.
        eventBus.on('updateinfo', (_info) => {
            this.ensureScrolled(false);
        });

        this.screenState.registerStateChangeCallback(() => {
            this.updateSize();
        });

        this.updateSize();

        // Set up custom emotes, as well as normal emoji typeahead.
        this.autocompleteOptions = [];
        this.emojiSearchOptions = [];
        for (const [key, value] of Object.entries(emojis)) {
          this.autocompleteOptions.push({text: key, type: "emoji", preview: twemoji.parse(value, twemojiOptions)});
          this.emojiSearchOptions.push({text: key, type: "emoji", preview: twemoji.parse(value, {...twemojiOptions, ...searchOptions})});
        }
        for (const [key, value] of Object.entries(emotes)) {
          this.autocompleteOptions.push({text: key, type: "emote", preview: "<img class=\"emoji-preview\" src=\"" + value + "\" />"});
          this.emojiSearchOptions.push({text: key, type: "emote", preview: "<img class=\"emoji-preview\" src=\"" + value + "\" loading=\"lazy\" />"});
        }
        this.emojisearchUpdate = emojisearch(this.inputState, '.emoji-search', '#message', this.emojiSearchOptions);

        // Support tab-completing users as well.
        this.autocompleteUpdate = autocomplete(this.inputState, '#message', this.autocompleteOptions);

        // Set up the emoji search itself.
        $(".emoji-search").html(twemoji.parse(String.fromCodePoint(0x1F600), twemojiOptions));
    }

    updateSize() {
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

    updateLastAction( action ) {
        if (!this.lastAction?.order) {
            this.lastAction = action;
        } else {
            if (action.order > this.lastAction.order) {
                this.lastAction = action;
            }
        }
    }

    setProfile( _profile ) {
        // This page intentionally left blank.
    }

    setPreferences( preferences ) {
        this.preferences = preferences;
        this.combineMessages(true);
    }

    setLastSettings( _settings ) {
        // This page intentionally left blank.
    }

    setOccupants( roomid, occupants ) {
        if (roomid == this.roomid) {
            this.occupants = occupants.filter((occupant) => !occupant.inactive);
            this.occupants.sort((a, b) => { return a.username.localeCompare(b.username); });
            this.occupantsLoaded = true;
            this.updateUsers();
        }
    }

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

    setRoom( roomid ) {
        if (this.roomsLoaded) {
            this.pendingroomid = "";
            if (roomid != this.roomid) {
                if (this.rooms.has(roomid)) {
                    this.messages = [];
                    this.roomid = roomid;
                    this.lastAction = {};
                    this.autoscroll = true;
                    this.occupants = [];
                    this.occupantsLoaded = false;
                    this.roomType = this.rooms.get(roomid).type;
                    this.updateUsers();

                    $('div.chat > div.conversation-wrapper > div.conversation').empty();
                    $( '#message-actions' ).attr('roomid', roomid);
                }
            }
        } else {
            this.pendingroomid = roomid;
        }
    }

    closeRoom( roomid ) {
        if (roomid == this.roomid) {
            this.message = [];
            this.roomid = "";
            this.lastAction = {};
            this.autoscroll = true;
            this.occupants = [];
            this.occupantsLoaded = false;
            this.updateUsers();

            $('div.chat > div.conversation-wrapper > div.conversation').empty();
            $( '#message-actions' ).attr('roomid', '');
        }
    }

    ensureScrolled( causedByNewMessage ) {
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

    updateHistory( roomid, history, lastSeen ) {
        if (roomid != this.roomid) {
            // Must be an out of date lookup, ignore it.
            return;
        }

        this.drawActions( history );

        if ( lastSeen ) {
            this.addNewIndicator( lastSeen );
        }
    }

    isNewIndicatorPresent() {
        return $('div.newseparator').length > 0;
    }

    addNewIndicator( lastSeen ) {
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

            this.removeNewIndicator();
            $(html).insertAfter(messages.find('div.item#' + lastMessage.id));

            this.ensureScrolled(true);
        }
    }

    removeNewIndicator() {
        $('div.newseparator').remove();
        this.ensureScrolled(true);
    }

    updateActions( roomid, actions ) {
        if (roomid != this.roomid) {
            // Must be an out of date lookup, ignore it.
            return;
        }

        // If this action is not visible, calculate the last seen message so we can add the new message indicator
        // to the current page.
        const lastSeenMessage = (this.visibility == "hidden" || !this.autoscroll) ? this.getLatestMessage() : undefined;

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
            this.updateUsers();
        }

        this.drawActions( actions );

        if (this.visibility == "hidden" && lastSeenMessage && !this.isNewIndicatorPresent()) {
            // Add a new messages line if we're in another tab, so we can tab back to new messages.
            this.addNewIndicator( lastSeenMessage.id );
        } else if (!this.autoscroll && lastSeenMessage && !this.isNewIndicatorPresent()) {
            // Add a new messgaes line if we're scrolled up, so we can scroll down to new messages.
            this.addNewIndicator( lastSeenMessage.id );
        } else if (selfMessage) {
            // We messaged this channel so nothing is new, we've seen it all.
            this.removeNewIndicator();
        }
    }

    drawOlderMessagesLoader() {
        // Remove any scroll detectors and add a new one at the top.
        $( '.scrolled-top' ).remove();

        if (this.roomid && this.rooms.has(this.roomid)) {
            const lowestMessage = this.getEarliestMessage();
            const room = this.rooms.get(this.roomid);

            if (room.oldest_action && lowestMessage && room.oldest_action != lowestMessage.id) {
                $('div.chat > div.conversation-wrapper > div.conversation').prepend('<div class="scrolled-top untriggered">...</div>');
            }
        }
    }

    loadOlderMessages() {
        var lowestMessage = this.getEarliestMessage();
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

    scrollToMessage() {
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

    getEarliestMessage() {
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

    getEarliestMessageOrder() {
        var lowestMessage = this.getEarliestMessage();
        return lowestMessage ? lowestMessage.order : -1;
    }

    getLatestMessage() {
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

    getLatestMessageOrder() {
        var highestMessage = this.getLatestMessage();
        return highestMessage ? highestMessage.order : -1;
    }

    drawActions( history ) {
        var lowestorder = this.getEarliestMessageOrder();
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

        prepend.forEach((message) => this.drawMessage(message, 'before'));
        append.forEach((message) => this.drawMessage(message, 'after'));

        this.combineMessages(false);
        this.drawOlderMessagesLoader();
        this.scrollToMessage();

        if (this.lastAction.id != oldactionid) {
            this.eventBus.emit("lastaction", {"roomid": this.roomid, "actionid": this.lastAction.id})
        }
    }

    // Whenever user changes occur (joins/parts/renames), update the autocomplete typeahead for those names.
    updateUsers() {
        var acusers = this.occupants.map(function(user) {
            return {
                text: "@" + user.username,
                type: "user",
                preview: "<img class=\"icon-preview\" src=\"" + user.icon + "\" />&nbsp;<span dir=\"auto\">" + escapeHtml(user.nickname) + "</span>",
            };
        });
        this.autocompleteUpdate(this.autocompleteOptions.concat(acusers));
    }

    // Whenever an emote is live-added, update the autocomplete typeahead for that emote.
    addEmotes( mapping ) {
        for (const [alias, uri] of Object.entries(mapping)) {
            emotes[alias] = uri;
            this.autocompleteOptions.push({text: alias, type: "emote", preview: "<img class=\"emoji-preview\" src=\"" + uri + "\" />"});
            this.emojiSearchOptions.push({text: alias, type: "emote", preview: "<img class=\"emoji-preview\" src=\"" + uri + "\" loading=\"lazy\" />"});
        }

        this.emojisearchUpdate(this.emojiSearchOptions);
        this.updateUsers();
    }

    // Whenever an emote is live-removed, update the autocomplet typeahead to remove that emote.
    deleteEmotes( aliases ) {
        aliases.forEach((alias) => {
            delete emotes[alias];
            this.autocompleteOptions = this.autocompleteOptions.filter((option) => !(option.type == "emote" && option.text == alias));
            this.emojiSearchOptions = this.emojiSearchOptions.filter((option) => !(option.type == "emote" && option.text == alias));
        });
        this.emojisearchUpdate(this.emojiSearchOptions);
        this.updateUsers();
    }

    formatMessage( message ) {
        return linkifyHtml(this.embiggen(this.highlight(escapeHtml(message))), linkifyOptions);
    }

    wasHighlighted( message ) {
        const escaped = escapeHtml(message);
        const actualuser = escapeHtml('@' + window.username);
        return containsStandaloneText(escaped, actualuser);
    }

    drawMessage( message, loc ) {
        // First, see if this is an update.
        var messages = $('div.chat > div.conversation-wrapper > div.conversation');
        var drawnMessage = messages.find('div.message#' + message.id);
        if (drawnMessage.length > 0) {
            if (message.action == "message") {
                let content = this.formatMessage(message.details);
                let highlighted = this.wasHighlighted(message.details);
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
                let content = this.formatMessage(message.details);
                let highlighted = this.wasHighlighted(message.details);

                html  = '<div class="item" id="' + message.id + '">';
                html += '  <div class="icon avatar" id="' + message.occupant.id + '">';
                html += '    <img src="' + message.occupant.icon + '" />';
                html += '  </div>';
                html += '  <div class="content-wrapper">';
                html += '    <div class="meta-wrapper">';
                html += '      <span class="name" dir="auto" id="' + message.occupant.id + '">' + escapeHtml(message.occupant.nickname) + '</span>';
                html += '      <span class="timestamp">' + formatDateTime(message.timestamp) + '</span>';
                html += '    </div>';
                html += '    <div class="message' + (highlighted ? " highlighted" : "") + '" dir="auto" id="' + message.id + '">' + content + '</div>';
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

            if (html) {
                if (loc == 'after') {
                    messages.append(html);
                    this.ensureScrolled(true);
                } else {
                    messages.prepend(html);
                }
            }
        }

        this.updateLastAction(message);
    }

    combineMessages( reflow ) {
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
            this.ensureScrolled(false);
        }
    }

    // Takes an alraedy HTML-stripped and emojified message and figures out if it contains only
    // emoji/emotes. If so, it makes them bigger because bigger emoji is more fun.
    embiggen( msg ) {
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

    // Walks an already HTML-stripped and emojified message to see if any part of it is a reference
    // to the current user. If so, wraps that chunk of text in a highlight div, but does not change
    // capitalization. This allows your own name to be highlighted without rewriting how somebody
    // wrote the message.
    highlight( msg ) {
        var actualuser = escapeHtml('@' + window.username).toLowerCase();

        if( msg.length < actualuser.length ) {
            return msg;
        }

        var before = '<span class="name-highlight" dir="auto">';
        var after = '</span>';
        var pos = 0;
        while (pos <= (msg.length - actualuser.length)) {
            if (pos > 0) {
                if (msg.substring(pos - 1, pos) != " ") {
                    pos ++;
                    continue;
                }
            }
            if (pos < (msg.length - actualuser.length)) {
                if (msg.substring(pos + actualuser.length, pos + actualuser.length + 1) != " ") {
                    pos ++;
                    continue;
                }
            }

            if (msg.substring(pos, pos + actualuser.length).toLowerCase() != actualuser) {
                pos++;
                continue;
            }

            msg = (
                msg.substring(0, pos) +
                before +
                msg.substring(pos, pos + actualuser.length) +
                after +
                msg.substring(pos + actualuser.length, msg.length)
            );

            pos += actualuser.length + before.length + after.length;
        }

        return msg;
    }
}

export { Messages };
