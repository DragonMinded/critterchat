import $ from "jquery";
import linkifyHtml from "linkify-html";
import { escapeHtml } from "../utils.js";

const linkifyOptions = { defaultProtocol: "http", target: "_blank", validate: { email: () => false } };

/**
 * Handles the profile view popover which is summoned when a user clicks on another user's
 * name in the info list or in chat.
 */
class Profile {
    constructor( eventBus ) {
        this.eventBus = eventBus;
        this.userid = undefined;

        $('#profile-form').on('submit', (event) => {
            event.stopPropagation();
        });

        $('#profile-message').on('click', (event) => {
            event.stopPropagation();
            event.stopImmediatePropagation();

            if (this.userid) {
                $.modal.close();
                this.eventBus.emit('joinroom', this.userid);
            }
        });

        $('#profile-deactivate').on('click', (event) => {
            event.stopPropagation();
            event.stopImmediatePropagation();

            if (this.userid) {
                this.eventBus.emit('admin', {action: 'deactivate', userid: this.userid});
            }
        });
    }

    /**
     * Called whenever a profile is loaded for display by the server.
     */
    setProfile( profile ) {
        // Populate the profile with our loaded results.
        $('#profile-form #profile-icon').attr('src', profile.icon);
        $('#profile-form #profile-nickname').html(escapeHtml(profile.nickname));

        if (profile.about) {
            $('#profile-form #profile-about').html(linkifyHtml(escapeHtml(profile.about), linkifyOptions));
            $('#profile-form #profile-about').removeClass('empty');;
        } else {
            $('#profile-form #profile-about').html("This chatter has not written a profile.");
            $('#profile-form #profile-about').addClass('empty');;
        }

        // Hide loading indicator, show profile.
        $('#profile-form div.loading').hide();
        $('#profile-form div.profile').show();

        // Display admin and moderator actions if needed.
        if (window.admin) {
            $('#profile-form div.admin-wrapper').show();
        }

        // Ensure we can send chat requests to the right place.
        this.userid = profile.id;
    }

    /**
     * Called when we want to display a profile.
     */
    display() {
        $.modal.close();

        // Ensure we don't accidentally retain stale user IDs.
        this.userid = undefined;

        $('#profile-form div.admin-wrapper').hide();
        $('#profile-form div.loading').show();
        $('#profile-form div.profile').hide();
        $('#profile-form').modal();
    }
}

export { Profile };
