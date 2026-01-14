import $ from "jquery";
import { escapeHtml } from "../utils.js";

/**
 * Handles the profile view popover which is summoned when a user clicks on another user's
 * name in the info list or in chat.
 */
class Profile {
    constructor( eventBus ) {
        this.eventBus = eventBus;
    }

    /**
     * Called whenever a profile is loaded for display by the server.
     */
    setProfile( profile ) {
        // Populate the profile with our loaded results.
        $('#profile-form #profile-icon').attr('src', profile.icon);
        $('#profile-form #profile-nickname').html(escapeHtml(profile.nickname));

        // Hide loading indicator, show profile.
        $('#profile-form div.loading').hide();
        $('#profile-form div.profile').show();
    }

    /**
     * Called when we want to display a profile.
     */
    display() {
        $.modal.close();

        $('#profile-form div.loading').show();
        $('#profile-form div.profile').hide();
        $('#profile-form').modal();
    }
}

export { Profile };
