import { CHAT_SENT, CHAT_RECEIVED, MESSAGE_SENT, MESSAGE_RECEIVED, MENTIONED, AUDIO_PREFS } from "../common.js";

class AudioNotifications {
    constructor( eventBus ) {
        this.eventBus = eventBus;
        this.sounds = {};
        this.preferences = {};
        this.preferencesLoaded = false;

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

    cacheAudio() {
        this.sounds = {};
        AUDIO_PREFS.forEach((pref) => {
            const checked = this.preferences.audio_notifs.includes(pref);
            const sound = this.preferences.notif_sounds[pref];

            if (checked && sound) {
                this.sounds[pref] = new Audio(sound);
            }
        });
    }
}

export { AudioNotifications };
