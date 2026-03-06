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
        this.mode = undefined;
        this.roomid = "";
        this.preferences = {};

        $( '#search' ).on( 'input', (event) => {
            event.preventDefault();

            var searchValue = $('#search').val();

            if (this.mode == "search") {
                this.eventBus.emit('searchrooms', {'name': searchValue});
            }
            if (this.mode == "invite" && this.roomid) {
                this.eventBus.emit('searchusers', {'roomid': this.roomid, 'name': searchValue});
            }
        });

        $( '#search-chat' ).on( 'click', (event) => {
            event.preventDefault();
            this.inputState.setState("empty");

            this.showSearch();
        });

        $( '#invite-chatter' ).on( 'click', (event) => {
            event.preventDefault();

            this.inputState.setState("empty");
            var roomid = $( '#invite-chatter' ).attr('roomid');
            if ( roomid ) {
                this.showInvites(roomid);
            }
        });

        $( '#search-create-private-chat' ).on( 'click', (event) => {
            event.preventDefault();
            this.inputState.setState("empty");

            this._createChat();
        });

        $( '#search-create-public-room' ).on( 'click', (event) => {
            event.preventDefault();
            this.inputState.setState("empty");

            this._createRoom();
        });

        $( '#search-form' ).on( 'submit', (event) => {
            event.preventDefault();
        });
    }

    /**
     * Called when the user clicks on the "find or start chat" button.
     */
    showSearch() {
        // Clear out any previous search, ask the backend for default results.
        $( '#search' ).val("");
        this.populateSearchResults([]);
        this.eventBus.emit('searchrooms', {'name': ""})

        // Show or hide action buttons based on admin rights.
        if (window.admin && this.preferences.admin_controls == "visible") {
            $('#search-create-public-room').show();
        } else {
            $('#search-create-public-room').hide();
        }
        $( '#search' ).attr('placeholder', "Find a chatter or an existing chat...")

        this.mode = "search";
        this.roomid = "";

        // Finally, display the modal.
        $('#search-form div.actions-wrapper').show();
        $('#search-form').modal();
        $('#search').focus();
    }

    /**
     * Called when the user clicks on the "send invite" button.
     */
    showInvites( roomid ) {
        // Clear out any previous search, ask the backend for default results.
        $( '#search' ).val("");
        this.populateSearchResults([]);
        this.eventBus.emit('searchusers', {'roomid': roomid, 'name': ""});

        this.mode = "invite";
        this.roomid = roomid;

        // Finally, display the modal.
        $('#search-form div.actions-wrapper').hide();
        $('#search').attr('placeholder', "Find a chatter to invite...")
        $('#search-form').modal();
        $('#search').focus();
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
            var type = result.type == "room" ? 'room' : 'avatar';
            var actionclass = "action";
            var hook = true;

            if (this.mode == "search") {
                if (result.roomid) {
                    action = result.joined ? "jump" : (result.invited ? "accept invite" : "join");
                } else {
                    action = "message";
                }
            }
            if (this.mode == "invite") {
                action = result.joined ? "already present" : (result.invited ? "already invited" : "invite");
                if (result.joined || result.invited) {
                    actionclass += " grayed";
                    hook = false;
                }
            }

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
            if (action) {
                html    += '  <div class="action-wrapper"><div class="' + actionclass + '">' + action + '</div></div>';
            }
            html    += '</div>';
            resultdom.append(html);

            if (this.mode == "search" && hook) {
                $('div.search > div.results div.item#' + id).on('click', (event) => {
                    event.stopPropagation();
                    event.stopImmediatePropagation();

                    var id = $(event.currentTarget).attr('id')
                    this._joinRoom( id );
                });
            }

            if (this.mode == "invite" && hook) {
                $('div.search > div.results div.item#' + id).on('click', (event) => {
                    event.stopPropagation();
                    event.stopImmediatePropagation();

                    var id = $(event.currentTarget).attr('id')
                    this._inviteToRoom( id );
                });
            }
        });
    }

    /**
     * Called when our parent informs us that the user's preferences have been updated. We only
     * care about the admin controls visibility preference here.
     */
    setPreferences( preferences ) {
        this.preferences = preferences;
    }

    /**
     * Called internally when we want to create a new private chat.
     */
    _createChat() {
        $.modal.close();
        $( '#search' ).val("");
        this.populateSearchResults([]);
        this.eventBus.emit('newroom', {'type': 'chat'});
    }

    /**
     * Called internally when we want to create a new public room.
     */
    _createRoom() {
        $.modal.close();
        $( '#search' ).val("");
        this.populateSearchResults([]);
        this.eventBus.emit('createroom');
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

    /**
     * Called internally when we want to invite a user to our private chat room.
     */
    _inviteToRoom( id ) {
        $.modal.close();
        $( '#search' ).val("");
        this.populateSearchResults([]);

        if (this.roomid) {
            this.eventBus.emit('inviteroom', {'roomid': this.roomid, 'userid': id});
        }
    }
}

export { Search };
