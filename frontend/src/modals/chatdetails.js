import $ from "jquery";
import { flash } from "../utils.js";
import { autocomplete } from "../components/autocomplete.js";

/**
 * Handles the chat details popover which is summoned and managed by the info panel
 * and allows the user to modify the room name, topic and custom icon.
 */
class ChatDetails {
    constructor( eventBus, inputState ) {
        this.eventBus = eventBus;
        this.inputState = inputState;
        this.preferences = {};
        this.room = {};
        this.action = undefined;
        this.icon = "";
        this.iconDelete = false;

        $( '#chatdetails-form' ).on( 'submit', (event) => {
            event.preventDefault();
        });

        $( '#chatdetails-confirm' ).on( 'click', (event) => {
            event.preventDefault();
            $.modal.close();
            this.inputState.setState("empty");

            if (this.action == "edit") {
                this.eventBus.emit('updateroom', {'roomid': this.room.id, 'details': {
                    'name': $('#chatdetails-name').val().substring(0, 255),
                    'topic': $('#chatdetails-topic').val().substring(0, 255),
                    'moderated': $('form#chatdetails-form input[type=radio][name="moderation"]:checked').val() == "moderated",
                    'autojoin': $('form#chatdetails-form input[type=radio][name="autojoin"]:checked').val() == "on",
                    'icon': this.icon,
                    'icon_delete': this.iconDelete,
                }});

                this.action = undefined;
            }

            if (this.action == "create") {
                this.eventBus.emit('newroom', {
                    'name': $('#chatdetails-name').val().substring(0, 255),
                    'topic': $('#chatdetails-topic').val().substring(0, 255),
                    'moderated': $('form#chatdetails-form input[type=radio][name="moderation"]:checked').val() == "moderated",
                    'autojoin': $('form#chatdetails-form input[type=radio][name="autojoin"]:checked').val() == "on",
                    'icon': this.icon,
                    'type': 'room',
                });

                this.action = undefined;
            }
        });

        $( '#chatdetails-cancel' ).on( 'click', (event) => {
            event.preventDefault();
            $.modal.close();
            this.inputState.setState("empty");

            this.action = undefined;
        });

        $( '#chatdetails-remove-icon' ).on( 'click', (event) => {
            event.preventDefault();
            this.icon = "";
            this.iconDelete = true;

            $( '#chatdetails-icon' ).attr('src', this.room['deficon']);
        });

        $( '#chatdetails-iconpicker' ).on( 'change', (event) => {
            const file = event.target.files[0];

            if (file && file.size < window.maxiconsize * 1024) {
                var fr = new FileReader();
                fr.onload = () => {
                    this.icon = fr.result;
                    this.iconDelete = false;
                    $( '#chatdetails-icon' ).attr('src', this.icon);
                };
                fr.readAsDataURL(file);
            } else {
                flash(
                    'warning',
                    'Chosen room icon file size is too large. Room icons cannot be larger than ' + window.maxiconsize + 'kb.'
                );
            }
        });

        // Set up emoji/emote autocomplete popover.
        this.autocompleteOptions = [];
        for (const [key, value] of Object.entries(window.emojis)) {
            this.autocompleteOptions.push(
                {text: key, type: "emoji", preview: twemoji.parse(value, twemojiOptions)}
            );
        }
        for (const [key, value] of Object.entries(window.emotes)) {
            const src = "src=\"" + value.uri + "\"";
            const dims = "width=\"" + value.dimensions[0] + "\" height=\"" + value.dimensions[1] + "\"";

            this.autocompleteOptions.push(
                {text: key, type: "emote", preview: "<img class=\"emoji-preview\" " + src + " " + dims + " />"}
            );
        }
        this.autocompleteUpdate = [];
        this.autocompleteUpdate.push(autocomplete(this.inputState, '#chatdetails-name', this.autocompleteOptions));
        this.autocompleteUpdate.push(autocomplete(this.inputState, '#chatdetails-topic', this.autocompleteOptions));
    }

    /**
     * Called whenever the manager is notified of new custom emotes that were added to the server. Whenever
     * an emote is live-added, update the autocomplete typeahead.
     */
    addEmotes( mapping ) {
        for (const [alias, details] of Object.entries(mapping)) {
            const src = "src=\"" + details.uri + "\"";
            const dims = "width=\"" + details.dimensions[0] + "\" height=\"" + details.dimensions[1] + "\"";

            this.autocompleteOptions.push(
                {text: alias, type: "emote", preview: "<img class=\"emoji-preview\" " + src + " " + dims + " />"}
            );
        }

        this.autocompleteUpdate.forEach((fun) => {
            fun(this.autocompleteOptions);
        });
    }

    /**
     * Called whenever the manager is notified of custom emotes that were removed from the server. Whenever
     * an emote is live-removed, update the autocomplete typeahead.
     * emote.
     */
    deleteEmotes( aliases ) {
        aliases.forEach((alias) => {
            this.autocompleteOptions = this.autocompleteOptions.filter((option) => !(option.type == "emote" && option.text ==       alias));
        });

        this.autocompleteUpdate.forEach((fun) => {
            fun(this.autocompleteOptions);
        });
    }

    /**
     * Called when our parent component wants us to be displayed on the screen. Causes us to
     * close any existing modal, open the chat details modal, and render the various details
     * for the room onto the DOM by finding the correct elements to update.
     */
    edit( room ) {
        this.room = room;

        $.modal.close();

        // Mark that we're editing.
        this.action = "edit";

        $( '#chatdetails-confirm' ).text('update info');
        this._display();
    }

    create() {
        this.room = {
            'public': true,
            'type': 'room',
            'moderated': false,
            'autojoin': false,
            'customname': '',
            'topic': '',
            'icon': window.defroom,
            'deficon': window.defroom,
        };

        $.modal.close();

        // Mark that we're creating.
        this.action = "create";

        $( '#chatdetails-confirm' ).text('create room');
        this._display();
    }

    _display() {
        // Start with a fresh form (clear bad file inputs).
        $('#chatdetails-form')[0].reset()

        // Display any server configured limits.
        $('#chatdetails-max-icon-width').text(window.maxicondimensions[0]);
        $('#chatdetails-max-icon-height').text(window.maxicondimensions[1]);
        $('#chatdetails-max-icon-size').text(window.maxiconsize);

        // Make sure we don't accidentally set a previous icon.
        this.icon = "";
        this.iconDelete = false;

        var photoType = this.room['public'] ? 'room' : 'avatar';
        $('div.chatdetails div.icon').removeClass('avatar').removeClass('room').addClass(photoType);

        var roomType = this.room.type == "room" ? "room" : "chat";
        $("#chatdetails-name-label").text(roomType + " name");
        $("#chatdetails-name").attr('placeholder', 'Type a custom name for this ' + roomType + '...');
        $("#chatdetails-topic-label").text(roomType + " topic");
        $("#chatdetails-topic").attr('placeholder', 'Type a topic for this ' + roomType + '...');

        // Only show moderator options for admins.
        if (window.admin && this.preferences.admin_controls == "visible" && this.room.type == "room") {
            $("form#chatdetails-form dl.moderation").show();
            $('form#chatdetails-form  input[type=radio][name="moderation"]').val([
                this.room.moderated ? "moderated" : "free-for-all"
            ]);

            $("form#chatdetails-form dl.autojoin").show();
            $('form#chatdetails-form  input[type=radio][name="autojoin"]').val([
                this.room.autojoin ? "on" : "off"
            ]);
        } else {
            $("form#chatdetails-form dl.moderation").hide();
            $("form#chatdetails-form dl.autojoin").hide();
        }

        $('#chatdetails-name').val(this.room.customname);
        $('#chatdetails-topic').val(this.room.topic);
        $('#chatdetails-icon').attr('src', this.room.icon);
        $('#chatdetails-form').modal();
    }

    /**
     * Called when our parent informs us that the user's preferences have been updated. We only
     * care about the admin controls visibility preference here.
     */
    setPreferences( preferences ) {
        this.preferences = preferences;
    }
}

export { ChatDetails };
