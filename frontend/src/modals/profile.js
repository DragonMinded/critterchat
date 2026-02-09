import $ from "jquery";
import linkifyHtml from "linkify-html";
import { ACTIVATED, ADMINISTRATOR } from "../common.js";
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
        this.profileid = undefined;
        this.preferences = {};

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

        $('#profile-activate').on('click', (event) => {
            event.stopPropagation();
            event.stopImmediatePropagation();

            if (this.userid) {
                this.eventBus.emit('admin', {action: 'activate', userid: this.userid});
            }
        });

        $('#profile-deactivate').on('click', (event) => {
            event.stopPropagation();
            event.stopImmediatePropagation();

            if (this.userid) {
                this.eventBus.emit('admin', {action: 'deactivate', userid: this.userid});
            }
        });

        $('#profile-mod').on('click', (event) => {
            event.stopPropagation();
            event.stopImmediatePropagation();

            if (this.userid) {
                this.eventBus.emit('admin', {action: 'mod', occupantid: this.profileid});
            }
        });

        $('#profile-demod').on('click', (event) => {
            event.stopPropagation();
            event.stopImmediatePropagation();

            if (this.userid) {
                this.eventBus.emit('admin', {action: 'demod', occupantid: this.profileid});
            }
        });

        this.eventBus.on('adminack', (response) => {
            const id = this.profileid || this.userid;
            if (id) {
                if (
                    response.action == "activate" ||
                    response.action == "deactivate" ||
                    response.action == "mod" ||
                    response.action == "demod"
                ) {
                    // Reload profile.
                    this.eventBus.emit('refreshprofile', id);
                }
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
        if (window.admin && this.preferences.admin_controls == "visible") {
            $('#profile-form div.admin-wrapper').show();

            // Allow any user to be activated or deactivated.
            if (profile.permissions.indexOf(ACTIVATED) >= 0) {
                $('#profile-form #profile-activate').hide();
                $('#profile-form #profile-deactivate').show();
            } else {
                $('#profile-form #profile-activate').show();
                $('#profile-form #profile-deactivate').hide();
            }

            // Don't want to set/revoke mod privileges on a global profile or on a user in a room that isn't
            // moderated. Only allow non-admins to be moderators, because admins are implicitly moderators already.
            if (this.room && this.room.type == "room" && this.room.moderated && profile.occupantid && profile.permissions.indexOf(ADMINISTRATOR) < 0) {
                if (profile.moderator) {
                    $('#profile-form #profile-mod').hide();
                    $('#profile-form #profile-demod').show();
                } else {
                    $('#profile-form #profile-mod').show();
                    $('#profile-form #profile-demod').hide();
                }
            } else {
                $('#profile-form #profile-mod').hide();
                $('#profile-form #profile-demod').hide();
            }
        }

        // Ensure we can send chat requests to the right place.
        this.userid = profile.id;
        this.profileid = profile.occupantid;
    }

    /**
     * Called when we want to display a profile. Takes an optional room (sometimes undefined
     * when this isn't called from clicking on a user in a room) that we're being displayed
     * in.
     */
    display( room ) {
        $.modal.close();

        // Ensure we don't accidentally retain stale user IDs.
        this.userid = undefined;
        this.profileid = undefined;
        this.room = room;

        $('#profile-form div.admin-wrapper').hide();
        $('#profile-form div.loading').show();
        $('#profile-form div.profile').hide();
        $('#profile-form').modal();
    }
}

export { Profile };
