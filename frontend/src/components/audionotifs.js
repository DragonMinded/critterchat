import { flash } from "../utils.js";

import { CHAT_SENT, MESSAGE_SENT, CHAT_RECEIVED, MESSAGE_RECEIVED, MENTIONED, USER_JOINED, USER_LEFT, AUDIO_PREFS } from "../common.js";

class AudioNotifications {
    constructor( eventBus ) {
        this.eventBus = eventBus;
        this.sounds = {};
        this.preferences = {};
        this.preferencesLoaded = false;
        this.verifiedAudio = false;

        this.eventBus.on( 'notification', (notif) => {
            var sound = undefined;
            if (notif.action == "messageSend") {
                if (notif.type == "room") {
                    sound = this.sounds[CHAT_SENT];
                } else {
                    sound = this.sounds[MESSAGE_SENT];
                }
            } else if (notif.action == "messageReceive") {
                if (notif.type == "room") {
                    sound = this.sounds[CHAT_RECEIVED];
                } else {
                    sound = this.sounds[MESSAGE_RECEIVED];
                }
            } else if (notif.action == "mention") {
                sound = this.sounds[MENTIONED];

                if (!sound) {
                    if (notif.type == "room") {
                        sound = this.sounds[CHAT_RECEIVED];
                    } else {
                        sound = this.sounds[MESSAGE_RECEIVED];
                    }
                }
            } else if (notif.action == "join") {
                sound = this.sounds[USER_JOINED];
            } else if (notif.action == "leave") {
                sound = this.sounds[USER_LEFT];
            } 

            if (sound) {
                sound.play();
            }
        });
    }

    setPreferences( preferences ) {
        this.preferences = preferences;
        this.preferencesLoaded = true;
        this.cacheAudio();
    }

    verifyAudio() {
        // Verifies that we can send audio notifications, and prompts to activate if we can't.
        const sound = new Audio(window.silence);
        sound.play()
            .catch(() => {
                flash(
                    'warning',
                    'You have audio notifications enabled but haven\'t allowed Autoplay for ' + window.appname +
                    '! Audio notifications will not work until you interact with the page or enable Autoplay.'
                );
            });
        this.verifiedAudio = true;
    }

    cacheAudio() {
        this.sounds = {};
        AUDIO_PREFS.forEach((pref) => {
            const checked = this.preferences.audio_notifs.includes(pref);
            const sound = this.preferences.notif_sounds[pref];

            if (checked && sound) {
                this.sounds[pref] = new Audio(sound);
                if (!this.verifiedAudio) {
                    this.verifyAudio();
                }
            }
        });
    }
}

export { AudioNotifications };
