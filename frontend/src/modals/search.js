import $ from "jquery";
import { escapeHtml } from "../utils.js";

/**
 * Handles the search popover which is the main entrypoint for finding rooms to join,
 * people to message, and existing rooms/chats that we are in to jump to that room.
 */
class Search {
    constructor( eventBus, inputState ) {
        this.eventBus = eventBus;
        this.inputState = inputState;

        $( '#search' ).on( 'input', (event) => {
            event.preventDefault();

            var searchValue = $('#search').val();
            this.eventBus.emit('searchrooms', searchValue);
        });

        $( '#search-chat' ).on( 'click', (event) => {
            event.preventDefault();
            this.inputState.setState("empty");
            $( '#search' ).val("");
            this.populateSearchResults([]);

            this.eventBus.emit('searchrooms', "")
            $('#search-form').modal();
            $('#search').focus();
        });

        $( '#search-form' ).on( 'submit', (event) => {
            event.preventDefault();
        });
    }

    /**
     * Called every time we have updated search results from the server based on a search event
     * that we generated. This function is responsible for updating the DOM to display the results.
     */
    populateSearchResults( results ) {
        var resultdom = $('div.search > div.results');
        resultdom.empty();

        results.forEach((result) => {
            var id = result.roomid || result.userid;
            var action = "";
            if (result.roomid) {
                action = result.joined ? "jump" : "join";
            } else {
                action = "message";
            }
            var type = result.type == "room" ? 'room' : 'avatar';

            var handleText = "";
            if (result.handle) {
                handleText = "<span>(" + escapeHtml(result.handle) + ")</span>";
            }

            var html = '<div class="item" id="' + id + '">';
            html    += '  <div class="icon ' + type + '">';
            html    += '    <img src="' + result.icon + '" />';
            if (result.type == 'room') {
                html    += '    <div class="room-indicator">#</div>';
            }
            html    += '  </div>';
            html    += '  <div class="name-wrapper"><div class="name">';
            html    += '    <span dir="auto">' + escapeHtml(result.name) + '</span>';
            html    += '    ' + handleText;
            html    += '  </div></div>';
            html    += '  <div class="action-wrapper"><div class="action">' + action + '</div></div>';
            html    += '</div>';
            resultdom.append(html);

            $('div.search > div.results div.item#' + id).on('click', (event) => {
                event.stopPropagation();
                event.stopImmediatePropagation();

                var id = $(event.currentTarget).attr('id')
                this._joinRoom( id );
            });
        });
    }

    /**
     * Called internally when we want to join a particular room. Note that regardless of the
     * printed call to action, under the hood we always treat this as a room join.
     */
    _joinRoom( id ) {
        $.modal.close();
        $( '#search' ).val("");
        this.populateSearchResults([]);
        this.eventBus.emit('joinroom', id);
    }
}

export { Search };
