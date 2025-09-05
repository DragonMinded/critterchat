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
                    'title_notifs': $('#editpreferences-title-notifications').is(":checked"),
                    'audio_notifs': set_audio_notifs,
                    'notif_sounds': this.newnotifications,
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

                    // Also auto-check since that would be a default assumption when uploading a file.
                    $('#editpreferences-audio-notification-' + key.toLowerCase()).prop('checked', true);

                    this.sounds[key] = new Audio(fr.result);
                    $('#editpreferences-audio-notification-' + key.toLowerCase() + '-preview').show();
                };
                fr.readAsDataURL(file);
            }
        });

        $( 'img.preview' ).on('click', (event) => {
            event.preventDefault();

            const jqe = $(event.target);
            var key = "";
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
    }

    display() {
        if (this.preferencesLoaded) {
            $.modal.close();

            $('#editpreferences-form').modal();
            $('#editpreferences-title-notifications').prop('checked', this.preferences.title_notifs);

            AUDIO_PREFS.forEach((pref) => {
                const checked = this.preferences.audio_notifs.includes(pref);
                const sound = this.preferences.notif_sounds[pref];

                $('#editpreferences-audio-notification-' + pref.toLowerCase()).prop('checked', checked);

                if (sound) {
                    this.sounds[pref] = new Audio(sound);
                    $('#editpreferences-audio-notification-' + pref.toLowerCase() + '-preview').show();
                } else {
                    $('#editpreferences-audio-notification-' + pref.toLowerCase() + '-preview').hide();
                }
            });
        }
    }

    setPreferences( preferences ) {
        this.preferences = preferences;
        this.newnotifications = {};
        this.preferencesLoaded = true;
    }
}

export { EditPreferences };
