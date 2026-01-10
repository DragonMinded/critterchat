import { flash } from "../utils.js";

import { CHAT_SENT, MESSAGE_SENT, CHAT_RECEIVED, MESSAGE_RECEIVED, MENTIONED, USER_JOINED, USER_LEFT, AUDIO_PREFS } from "../common.js";

/**
 * Audio notification handling component. This is responsible for listening for
 * notification events on the event bus and translating those to actual audio
 * notifications played in the browser. This handles detecting if autoplay has
 * been disabled as well as handling which audio file to play based on the user's
 * preferences and the notification type that has occurred.
 */
class AudioNotifications {
    constructor( eventBus, initialSize, initialVisibility ) {
        this.eventBus = eventBus;
        this.size = initialSize;
        this.visibility = initialVisibility;
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

        eventBus.on( 'resize', (newSize) => {
            this.size = newSize;
            this._cacheAudio();
        });

        eventBus.on( 'updatevisibility', (newVisibility) => {
            this.visibility = newVisibility;
        });
    }

    /**
     * Called every time the server informs us that preferences were updated, as well as once every
     * connection success or reconnect. The preferences include the actual audio URIs that we should
     * play as well as whether each notification type is enabled. After a preferences update, we
     * cache the audio so that we can grab it and play it when needed.
     */
    setPreferences( preferences ) {
        this.preferences = preferences;
        this.preferencesLoaded = true;
        this._cacheAudio();
    }

    /**
     * Verifies that we have permission to play audio by playing a known silence audio file. If
     * we do not, we flash a warning to the screen that autoplay is disabled. This serves two
     * purposes. First, it lets the user know that they might not receive audio notifications that
     * they expected, and second, by clicking to dismiss the flash, this enables audio notifications
     * in most browsers since it's considered an interaction.
     */
    _verifyAudio() {
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

    /**
     * Cache audio into an internal array so that we can simply play it back in the notification
     * event handler. We also re-cache every time we transition from mobile to desktop or desktop
     * to mobile size, since there's a setting for enabling audio on mobile that we wish to preserve.
     * The event handler is dumb and only looks for a cached sound, so we handle both sound enable
     * globally as well as individual sound enables here by only caching a given sound if it has
     * been configured and enabled, and the global notifications haven't been disabled for mobile.
     */
    _cacheAudio() {
        // Start with a clean slate so that we can delete existing sounds if they're disabled.
        this.sounds = {};

        const mobile_notifs = this.preferences.mobile_audio_notifs;
        if (this.size == "mobile" && !mobile_notifs) {
            return;
        }

        AUDIO_PREFS.forEach((pref) => {
            const checked = this.preferences.audio_notifs.includes(pref);
            const sound = this.preferences.notif_sounds[pref];

            if (checked && sound) {
                this.sounds[pref] = new Audio(sound);
                if (!this.verifiedAudio) {
                    this._verifyAudio();
                }
            }
        });
    }
}

export { AudioNotifications };
