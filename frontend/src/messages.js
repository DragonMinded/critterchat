import $ from "jquery";

// Importing this enables linkify-html below.
import * as linkify from "linkifyjs"; // eslint-disable-line no-unused-vars
import linkifyHtml from "linkify-html";

import { escapeHtml, formatTime, scrollTop, scrollTopMax } from "./utils.js";
import { emojisearch } from "./components/emojisearch.js";
import { autocomplete } from "./components/autocomplete.js";

const linkifyOptions = { defaultProtocol: "http", target: "_blank", validate: { email: () => false } };

class Messages {
    constructor( eventBus, inputState ) {
        this.eventBus = eventBus;
        this.inputState = inputState;
        this.messages = [];
        this.occupants = [];
        this.roomid = "";
        this.autoscroll = true;
        this.lastAction = {};
        this.lastSettings = {};
        this.lastSettingsLoaded = false;
        this.occupantsLoaded = false;

        $( '#message-actions' ).on( 'submit', (event) => {
            event.preventDefault();

            this.inputState.setState("empty");
            var roomid = $( '#message-actions' ).attr('roomid');

            if (roomid) {
                var message = $( 'input#message' ).val();
                $( 'input#message' ).val( '' );

                if (message) {
                    this.eventBus.emit('message', {'roomid': roomid, 'message': message});
                }
            }
        });

        $( 'div.chat > div.conversation-wrapper' ).on( 'click', () => {
            this.inputState.setState("empty");
        });

        $( 'div.chat > div.conversation-wrapper' ).scroll(() => {
            var box = $( 'div.chat > div.conversation-wrapper' );
            this.autoscroll = scrollTop(box[0]) >= scrollTopMax(box[0]);
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
            this.autoscroll = scrollTop(box[0]) >= scrollTopMax(box[0]);
            if (this.autoscroll) {
                $( 'div.new-messages-alert' ).css( 'display', 'none' );
            }
        });

        // Set up custom emotes, as well as normal emoji typeahead.
        this.options = [];
        for (const [key, value] of Object.entries(emojis)) {
          this.options.push({text: key, type: "emoji", preview: twemoji.parse(value, twemojiOptions)});
        }
        for (const [key, value] of Object.entries(emotes)) {
          this.options.push({text: key, type: "emote", preview: "<img class=\"emoji-preview\" src=\"" + value + "\" />"});
        }
        this.emojisearchUpdate = emojisearch(this.inputState, '.emoji-search', '#message', this.options);

        // Support tab-completing users as well.
        this.autocompleteUpdate = autocomplete(this.inputState, '#message', this.options);

        // Set up the emoji search itself.
        $(".emoji-search").html(twemoji.parse(String.fromCodePoint(0x1F600), twemojiOptions));
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

    setLastSettings( settings ) {
        this.lastSettings = settings;
        this.lastSettingsLoaded = true;

        if (this.roomsLoaded) {
            this.selectRoom(this.lastSettings.roomid);
        }
    }

    setOccupants( roomid, occupants ) {
        if (roomid == this.roomid) {
            this.occupants = occupants.filter((occupant) => !occupant.inactive);
            this.occupants.sort((a, b) => { return a.username.localeCompare(b.username); });
            this.occupantsLoaded = true;
            this.updateUsers();
        }
    }

    setRoom( roomid ) {
        if (roomid != this.roomid) {
            this.messages = [];
            this.roomid = roomid;
            this.lastAction = {};
            this.autoscroll = true;
            this.occupants = [];
            this.occupantsLoaded = false;
            this.updateUsers();

            $('div.chat > div.conversation-wrapper > div.conversation').empty();
            $( '#message-actions' ).attr('roomid', roomid);
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

    ensureScrolled() {
        var box = $( 'div.chat > div.conversation-wrapper' );
        if (this.autoscroll) {
            box[0].scrollTop = scrollTopMax(box[0]) + 1;
        } else {
            $( 'div.new-messages-alert' ).css( 'display', 'inline-block' );
        }
    }

    updateHistory( roomid, history ) {
        if (roomid != this.roomid) {
            // Must be an out of date lookup, ignore it.
            return;
        }

        this.drawActions( history );
    }

    updateActions( roomid, actions ) {
        if (roomid != this.roomid) {
            // Must be an out of date lookup, ignore it.
            return;
        }

        // This is where we get notified of user joins and leaves.
        var changed = false;
        if (this.occupantsLoaded) {
            actions.forEach((message) => {
                if (message.action == "join") {
                    // Add a new occupant to our list.
                    this.occupants.push(message.occupant);
                    changed = true;
                } else if (message.action == "leave") {
                    this.occupants = this.occupants.filter((occupant) => occupant.id != message.occupant.id);
                    changed = true;
                }
            });
        }

        if (changed) {
            this.occupants.sort((a, b) => { return a.username.localeCompare(b.username); });
            this.updateUsers();
        }

        this.drawActions( actions );
    }

    drawActions( history ) {
        var lowestorder = -1;
        for (const message of this.messages) {
            if (lowestorder == -1) {
                lowestorder = message.order;
            } else {
                lowestorder = Math.min(lowestorder, message.order);
            }
        }

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
                preview: "<img class=\"icon-preview\" src=\"" + user.icon + "\" />&nbsp;" + escapeHtml(user.nickname)
            };
        });
        this.autocompleteUpdate(this.options.concat(acusers));
    }

    // Whenever an emote is live-added, update the autocomplete typeahead for that emote.
    addEmotes( mapping ) {
        var box = $( 'div.emote-preload' );

        for (const [alias, uri] of Object.entries(mapping)) {
            emotes[alias] = uri;
            this.options.push({text: alias, type: "emote", preview: "<img class=\"emoji-preview\" src=\"" + uri + "\" />"});

            // Also be sure to reload the image.
            box.append( '<img src="' + uri + '" />' );
        }

        this.emojisearchUpdate(this.options);
        this.updateUsers();
    }

    // Whenever an emote is live-removed, update the autocomplet typeahead to remove that emote.
    deleteEmotes( aliases ) {
        aliases.forEach((alias) => {
            delete emotes[alias];
            this.options = this.options.filter((option) => !(option.type == "emote" && option.text == alias));
        });
        this.emojisearchUpdate(this.options);
        this.updateUsers();
    }

    formatMessage( message ) {
        return linkifyHtml(this.embiggen(this.highlight(escapeHtml(message))), linkifyOptions);
    }

    wasHighlighted( message ) {
        var before = escapeHtml(message);
        var after = this.highlight(before);
        return before != after;
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

                html  = '<div class="item">';
                html += '  <div class="icon avatar" id="' + message.occupant.id + '">';
                html += '    <img src="' + message.occupant.icon + '" />';
                html += '  </div>';
                html += '  <div class="content-wrapper">';
                html += '    <div class="meta-wrapper">';
                html += '      <div class="name" id="' + message.occupant.id + '">' + escapeHtml(message.occupant.nickname) + '</div>';
                html += '      <div class="timestamp" id="' + message.id + '">' + formatTime(message.timestamp) + '</div>';
                html += '    </div>';
                html += '    <div class="message' + (highlighted ? " highlighted" : "") + '" id="' + message.id + '">' + content + '</div>';
                html += '  </div>';
                html += '</div>';
            } else if (message.action == "join") {
                html  = '<div class="item">';
                html += '  <div class="content-wrapper">';
                html += '    <div class="meta-wrapper">';
                html += '      <div class="name" id="' + message.occupant.id + '">' + escapeHtml(message.occupant.nickname) + '</div>';
                html += '      <div class="joinmessage">has joined!</div>';
                html += '      <div class="timestamp" id="' + message.id + '">' + formatTime(message.timestamp) + '</div>';
                html += '    </div>';
                html += '  </div>';
                html += '</div>';
            } else if (message.action == "leave") {
                html  = '<div class="item">';
                html += '  <div class="content-wrapper">';
                html += '    <div class="meta-wrapper">';
                html += '      <div class="name" id="' + message.occupant.id + '">' + escapeHtml(message.occupant.nickname) + '</div>';
                html += '      <div class="joinmessage">has left!</div>';
                html += '      <div class="timestamp" id="' + message.id + '">' + formatTime(message.timestamp) + '</div>';
                html += '    </div>';
                html += '  </div>';
                html += '</div>';
            }

            if (loc == 'after') {
                messages.append(html);
            } else {
                messages.prepend(html);
            }
        }

        this.updateLastAction(message);
        this.ensureScrolled();
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
        var actualuser = escapeHtml('@' + username).toLowerCase();

        if( msg.length < actualuser.length ) {
            return msg;
        }

        var before = '<span class="name-highlight">';
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
