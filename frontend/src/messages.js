import $ from "jquery";
import { escapehtml, formattime } from "./utils.js";

class Messages {
    constructor( eventBus ) {
        this.eventBus = eventBus;
        this.messages = [];
        this.roomid = "";
        this.lastSettings = {};
        this.lastSettingsLoaded = false;

        $( '#message-actions' ).on( 'submit', (event) => {
            event.preventDefault();

            var roomid = $( '#message-actions' ).attr('roomid');
            var message = $( 'input#message' ).val();
            $( 'input#message' ).val( '' );

            if (message) {
                this.eventBus.emit('message', {'roomid': roomid, 'message': message});
            }
        } );
    }

    setLastSettings( settings ) {
        this.lastSettings = settings;
        this.lastSettingsLoaded = true;

        if (this.roomsLoaded) {
            this.selectRoom(this.lastSettings.roomid);
        }
    }

    setRoom( roomid ) {
        if (roomid != this.roomid) {
            this.messages = [];
            this.roomid = roomid;

            $('div.chat > div.conversation').empty();
            $( '#message-actions' ).attr('roomid', roomid);
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

        prepend.forEach((message, i) => this.drawMessage(message, 'before'));
        append.forEach((message, i) => this.drawMessage(message, 'after'));

    }

    drawMessage( message, location ) {
        // First, see if this is an update.
        var messages = $('div.chat > div.conversation');
        var drawnMessage = messages.find('div.message#' + message.id);
        if (drawnMessage.length > 0) {
            drawnMessage.html(escapehtml(message.details));
        } else {
            // Now, draw it fresh since it's not an update.
            var html = '<div class="item">';
            html    += '  <div class="icon" id="' + message.occupant.id + '">';
            html    += '    <img src="' + message.occupant.icon + '" />';
            html    += '  </div>';
            html    += '  <div class="content-wrapper">';
            html    += '    <div class="meta-wrapper">';
            html    += '      <div class="name" id="' + message.occupant.id + '">' + message.occupant.nickname + '</div>';
            html    += '      <div class="timestamp" id="' + message.id + '">' + formattime(message.timestamp) + '</div>';
            html    += '    </div>';
            html    += '    <div class="message" id="' + message.id + '">' + escapehtml(message.details) + '</div>';
            html    += '  </div>';
            html    += '</div>';

            if (location == 'after') {
                messages.append(html);
            } else {
                messages.prepend(html);
            }
        }
    }
}

export { Messages };
