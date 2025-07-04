import $ from "jquery";
import { escapeHtml, formatTime, scrollTop, scrollTopMax } from "./utils.js";

class Messages {
    constructor( eventBus ) {
        this.eventBus = eventBus;
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

            var roomid = $( '#message-actions' ).attr('roomid');

            if (roomid) {
                var message = $( 'input#message' ).val();
                $( 'input#message' ).val( '' );

                if (message) {
                    this.eventBus.emit('message', {'roomid': roomid, 'message': message});
                }
            }
        });

        $( 'div.chat > div.conversation' ).scroll(() => {
            var box = $( 'div.chat > div.conversation' );
            this.autoscroll = scrollTop(box[0]) >= scrollTopMax(box[0]);
            if (this.autoscroll) {
                $( 'div.new-messages-alert' ).css( 'display', 'none' );
            }
        });

        $(window).resize(() => {
            var box = $( 'div.chat > div.conversation' );
            if (this.autoscroll) {
                box[0].scrollTop = scrollTopMax(box[0]) + 1;
            }

            // Recalculate autoscroll since it could have been enabled by a resize.
            this.autoscroll = scrollTop(box[0]) >= scrollTopMax(box[0]);
            if (this.autoscroll) {
                $( 'div.new-messages-alert' ).css( 'display', 'none' );
            }
        });
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

    setOccupants( occupants ) {
        this.occupants = occupants;
        this.occupantsLoaded = true;
    }

    setRoom( roomid ) {
        if (roomid != this.roomid) {
            this.messages = [];
            this.roomid = roomid;
            this.lastAction = {};
            this.autoscroll = true;

            $('div.chat > div.conversation').empty();
            $( '#message-actions' ).attr('roomid', roomid);
        }
    }

    closeRoom( roomid ) {
        if (roomid == this.roomid) {
            this.message = [];
            this.roomid = "";
            this.lastAction = {};
            this.autoscroll = true;
            $('div.chat > div.conversation').empty();
            $( '#message-actions' ).attr('roomid', '');
        }
    }

    ensureScrolled() {
        var box = $( 'div.chat > div.conversation' );
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

    drawMessage( message, loc ) {
        // First, see if this is an update.
        var messages = $('div.chat > div.conversation');
        var drawnMessage = messages.find('div.message#' + message.id);
        if (drawnMessage.length > 0) {
            if (message.action == "message") {
                drawnMessage.html(escapeHtml(message.details));
            }
        } else {
            // Now, draw it fresh since it's not an update.
            var html = "";
            if (message.action == "message") {
                html  = '<div class="item">';
                html += '  <div class="icon avatar" id="' + message.occupant.id + '">';
                html += '    <img src="' + message.occupant.icon + '" />';
                html += '  </div>';
                html += '  <div class="content-wrapper">';
                html += '    <div class="meta-wrapper">';
                html += '      <div class="name" id="' + message.occupant.id + '">' + message.occupant.nickname + '</div>';
                html += '      <div class="timestamp" id="' + message.id + '">' + formatTime(message.timestamp) + '</div>';
                html += '    </div>';
                html += '    <div class="message" id="' + message.id + '">' + escapeHtml(message.details) + '</div>';
                html += '  </div>';
                html += '</div>';
            } else if (message.action == "join") {
                html  = '<div class="item">';
                html += '  <div class="content-wrapper">';
                html += '    <div class="meta-wrapper">';
                html += '      <div class="name" id="' + message.occupant.id + '">' + message.occupant.nickname + '</div>';
                html += '      <div class="joinmessage">has joined!</div>';
                html += '      <div class="timestamp" id="' + message.id + '">' + formatTime(message.timestamp) + '</div>';
                html += '    </div>';
                html += '  </div>';
                html += '</div>';
            } else if (message.action == "leave") {
                html  = '<div class="item">';
                html += '  <div class="content-wrapper">';
                html += '    <div class="meta-wrapper">';
                html += '      <div class="name" id="' + message.occupant.id + '">' + message.occupant.nickname + '</div>';
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
}

export { Messages };
