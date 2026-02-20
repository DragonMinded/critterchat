import $ from "jquery";
import { flash } from "../utils.js";
import { autocomplete } from "../components/autocomplete.js";

/**
 * Handles the user profile popover which is summoned and managed by the menu panel.
 * This is where users edit their avatar as well as their nickname, and in the future
 * any other publicly displayable information such as other socials, sites, a bio, and
 * any sort of user customization we allow.
 */
class EditProfile {
    constructor( eventBus, inputState ) {
        this.eventBus = eventBus;
        this.inputState = inputState;
        this.profile = {};
        this.profileLoaded = false;
        this.icon = "";
        this.iconDelete = false;

        $( '#editprofile-form' ).on( 'submit', (event) => {
            event.preventDefault();
        });

        $( '#editprofile-confirm' ).on( 'click', (event) => {
            event.preventDefault();
            $.modal.close();
            this.inputState.setState("empty");

            if (this.profileLoaded) {
                this.eventBus.emit('updateprofile', {
                    'name': $('#editprofile-name').val().substring(0, 255),
                    'about': $('#editprofile-about').val().substring(0, window.maxabout),
                    'icon': this.icon,
                    'icon_delete': this.iconDelete,
                });
            }
        });

        $( '#editprofile-cancel' ).on( 'click', (event) => {
            event.preventDefault();
            $.modal.close();
            this.inputState.setState("empty");
        });

        $( '#editprofile-remove-icon' ).on( 'click', (event) => {
            event.preventDefault();
            this.icon = "";
            this.iconDelete = true;

            $( '#editprofile-icon' ).attr('src', window.defavi);
        });

        $( '#editprofile-iconpicker' ).on( 'change', (event) => {
            const file = event.target.files[0];

            if (file && file.size < window.maxiconsize * 1024) {
                var fr = new FileReader();
                fr.onload = () => {
                    this.icon = fr.result;
                    this.iconDelete = false;
                    $( '#editprofile-icon' ).attr('src', this.icon);
                };
                fr.readAsDataURL(file);
            } else {
                flash(
                    'warning',
                    'Chosen avatar file size is too large. Avatars cannot be larger than ' + window.maxiconsize + 'kb.'
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
        this.autocompleteUpdate.push(autocomplete(this.inputState, '#editprofile-name', this.autocompleteOptions));
        this.autocompleteUpdate.push(autocomplete(this.inputState, '#editprofile-about', this.autocompleteOptions));
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
     * close any existing modal, open the profile editor modal, and render the various bits of
     * the user's profile onto the DOM by finding the correct elements to update.
     */
    display() {
        if (this.profileLoaded) {
            $.modal.close();

            // Make sure we don't accidentally set a previous icon.
            this.icon = "";
            this.iconDelete = false;

            // Display any server configured limits.
            $('#editprofile-max-icon-width').text(window.maxicondimensions[0]);
            $('#editprofile-max-icon-height').text(window.maxicondimensions[1]);
            $('#editprofile-max-icon-size').text(window.maxiconsize);
            $('#editprofile-about').attr("maxlength", window.maxabout);

            // Display actual profile details.
            $('#editprofile-form')[0].reset();
            $('#editprofile-name').val(this.profile.nickname);
            $('#editprofile-about').val(this.profile.about);
            $('#editprofile-icon').attr('src', this.profile.icon);
            $('#editprofile-form').modal();
        }
    }

    /**
     * Called every time our parent informs us that our profile was updated, as well as once every
     * connection success or reconnect. We just use this to keep an updated copy of the profile so
     * we can display the info for edit on popover without needing to fetch from the server first.
     * Note that this doesn't handle any sort of live update, so if the user updates their profile
     * in another client while editing their profile in this client, those updates will not be
     * live updated here.
     */
    setProfile( profile ) {
        // Server sets the nickname field to the username field for easier display,
        // but that means we need to not pretend that our nickname is set to our
        // username if it's not set.
        if (profile.username == profile.nickname) {
            profile.nickname = "";
        }
        this.profile = profile;
        this.profileLoaded = true;
    }
}

export { EditProfile };
