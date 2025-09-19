import $ from "jquery";
import { AUDIO_PREFS } from "../common.js";

class EditPreferences {
    constructor( eventBus, inputState ) {
        this.eventBus = eventBus;
        this.inputState = inputState;
        this.preferences = {};
        this.preferencesLoaded = false;
        this.sounds = {};
        this.newnotifications = {};
        this.deletednotifications = {};

        $( '#editpreferences-form' ).on( 'submit', (event) => {
            event.preventDefault();
        });

        $( '#editpreferences-confirm' ).on( 'click', (event) => {
            event.preventDefault();
            $.modal.close();
            this.inputState.setState("empty");

            if (this.preferencesLoaded) {
                let set_audio_notifs = [];
                AUDIO_PREFS.forEach((pref) => {
                    if ($('#editpreferences-audio-notification-' + pref.toLowerCase()).prop('checked')) {
                        set_audio_notifs.push(pref);
                    }
                });

                this.eventBus.emit('updatepreferences', {
                    'rooms_on_top': $('#editpreferences-rooms-on-top').is(":checked"),
                    'color_scheme': $('input[type=radio][name="color-scheme"]:checked').val(),
                    'title_notifs': $('#editpreferences-title-notifications').is(":checked"),
                    'mobile_audio_notifs': $('#editpreferences-mobile-audio-notifications').is(":checked"),
                    'audio_notifs': set_audio_notifs,
                    'notif_sounds': this.newnotifications,
                    'notif_sounds_delete': Object.keys(this.deletednotifications),
                });
            }
        });

        $( '#editpreferences-cancel' ).on( 'click', (event) => {
            event.preventDefault();
            $.modal.close();
            this.inputState.setState("empty");
        });

        $( 'input.notification' ).on( 'change', (event) => {
            const jqe = $(event.target);
            const file = event.target.files[0];

            var key = "";
            AUDIO_PREFS.forEach((pref) => {
                const expected = 'editpreferences-audio-notification-' + pref.toLowerCase() + '-file';
                if (jqe.attr('id') == expected) {
                    key = pref;
                }
            });

            if (key && file && file.size < 128 * 1024) {
                var fr = new FileReader();
                fr.onload = () => {
                    this.newnotifications[key] = fr.result;
                    delete this.deletednotifications[key];

                    // Also auto-check since that would be a default assumption when uploading a file.
                    $('#editpreferences-audio-notification-' + key.toLowerCase()).prop('checked', true);

                    this.sounds[key] = new Audio(fr.result);

                    $('#editpreferences-audio-notification-' + key.toLowerCase() + '-preview').show();
                    $('#editpreferences-audio-notification-' + key.toLowerCase() + '-cancel').show();
                };
                fr.readAsDataURL(file);
            }
        });

        $( 'div.preview' ).on('click', (event) => {
            event.preventDefault();

            const jqe = $(event.target);
            var key = undefined;
            AUDIO_PREFS.forEach((pref) => {
                const expected = 'editpreferences-audio-notification-' + pref.toLowerCase() + '-preview';
                if (jqe.attr('id') == expected) {
                    key = pref;
                }
            });

            if (key && this.sounds[key]) {
                this.sounds[key].play();
            }
        });

        $( 'div.cancel' ).on('click', (event) => {
            event.preventDefault();

            const jqe = $(event.target);
            var key = undefined;
            AUDIO_PREFS.forEach((pref) => {
                const expected = 'editpreferences-audio-notification-' + pref.toLowerCase() + '-cancel';
                if (jqe.attr('id') == expected) {
                    key = pref;
                }
            });

            if (key) {
                delete this.sounds[key];
                delete this.newnotifications[key];
                this.deletednotifications[key] = "";

                $('#editpreferences-audio-notification-' + key.toLowerCase() + '-preview').hide();
                $('#editpreferences-audio-notification-' + key.toLowerCase() + '-cancel').hide();

                // Also auto-uncheck since that would be a default assumption when deleting a notification sound.
                $('#editpreferences-audio-notification-' + key.toLowerCase()).prop('checked', false);
            }
        });
    }

    display() {
        if (this.preferencesLoaded) {
            $.modal.close();

            // Make sure we don't have anything left over from last time.
            this.deletednotifications = {};
            this.newnotifications = {};

            $('#editpreferences-form')[0].reset();
            $('#editpreferences-rooms-on-top').prop('checked', this.preferences.rooms_on_top);
            $('#editpreferences-title-notifications').prop('checked', this.preferences.title_notifs);
            $('#editpreferences-mobile-audio-notifications').prop('checked', this.preferences.mobile_audio_notifs);
            $('input[type=radio][name="color-scheme"]').val([this.preferences.color_scheme]);

            AUDIO_PREFS.forEach((pref) => {
                const checked = this.preferences.audio_notifs.includes(pref);
                const sound = this.preferences.notif_sounds[pref];

                $('#editpreferences-audio-notification-' + pref.toLowerCase()).prop('checked', checked);

                if (sound) {
                    this.sounds[pref] = new Audio(sound);
                    $('#editpreferences-audio-notification-' + pref.toLowerCase() + '-preview').show();
                    $('#editpreferences-audio-notification-' + pref.toLowerCase() + '-cancel').show();
                } else {
                    $('#editpreferences-audio-notification-' + pref.toLowerCase() + '-preview').hide();
                    $('#editpreferences-audio-notification-' + pref.toLowerCase() + '-cancel').hide();
                }
            });
            $('#editpreferences-form').modal();
        }
    }

    setPreferences( preferences ) {
        this.preferences = preferences;
        this.newnotifications = {};
        this.deletednotifications = {};
        this.preferencesLoaded = true;
    }
}

export { EditPreferences };
