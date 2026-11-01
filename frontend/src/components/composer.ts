import $ from "jquery";

import { InputState } from "../inputstate";
import { ScreenState } from "../screenstate";
import { EventHandler } from "./event";
import { ID, Preferences, Occupant, Room } from "../types"

import { UploadPicker } from "./uploadpicker.js";
import { isPendingMessageSensitive } from "../utils";
import { displayInfo } from "../modals/infomodal.js";

// These are provided by the backend when it renders out the HTML we're part of.
declare global {
    interface Window {
        maxmessage: number;
        maxattachments: number;
        mimetypes: string[];
    }
}

interface Pending {
    message: string;
    sensitive: boolean;
}

/**
 * The class responsible specifically for the composer input and the send button. Keeps
 * track of what state we're in (edit message mode and normal mode) as well as saving
 * and restoring that state when rooms change. Also in charge of the upload picker.
 * Note that this doesn't handle the emoji search and autocomplete typeaheads, because
 * it was originally forked from the message top-level object and it's fairly entangled
 * there. This might change in the future with a clean-up.
 */
export class Composer {
    // Components and such we manage or access.
    eventBus: EventHandler;
    screenState: ScreenState;
    inputState: InputState;
    uploadPicker: UploadPicker;

    // Tracks who we are, so we can determine if the send button should stay greyed out.
    myself: Occupant | undefined;

    // Tracks room information passed to us from our parent.
    roomsLoaded: boolean;
    rooms: Map<ID, Room>;
    roomid: string;

    // Tracks whether we're connected, for greying out the send button.
    connected: boolean;

    // Track any pending text based on room.
    pending: Map<ID, Pending>;

    // Handles making sure you can't mess with or double-post a message when one is sending.
    awaitingResponse: Map<ID, boolean>;

    constructor( eventBus: EventHandler, screenState: ScreenState, inputState: InputState ) {
        this.eventBus = eventBus;
        this.screenState = screenState;
        this.inputState = inputState;
        this.myself = undefined;
        this.roomsLoaded = false;
        this.rooms = new Map();
        this.roomid = "";
        this.connected = false;
        this.pending = new Map();
        this.awaitingResponse = new Map();

        $( '#message-actions' ).on( 'submit', (event) => {
            event.preventDefault();

            this.inputState.setState("empty");

            const roomid = $( '#message-actions' ).attr('roomid');
            if (roomid) {
                if (this.awaitingResponse.has(roomid) && this.awaitingResponse.get(roomid)) {
                    // Skip out on this, we're waiting for a server response so we shouldn't duplicate
                    // the message.
                    return;
                }

                // Grab message, focus on the message box if we clicked send.
                const curVal = $( 'input#message' ).val();
                const message = curVal ? String(curVal) : "";

                $( 'input#message' ).focus();
                if (message.length > window.maxmessage) {
                    displayInfo(
                        'Your message is too long to be sent, please type fewer things!',
                        'okay!',
                    );
                } else {
                    // First, grab any attachments that should go with the message.
                    const files = this.uploadPicker.files( roomid );

                    if (message.length > 0 || files.length > 0) {
                        // Prevent double-click from causing a double-send of messages.
                        this.awaitingResponse.set(roomid, true);

                        // Now, send the event.
                        this.eventBus.emit(
                            'message',
                            {
                                'roomid': roomid,
                                'message': message,
                                'sensitive': isPendingMessageSensitive(),
                                'attachments': files,
                            },
                        );
                    }
                }
            }
        });

        $( document ).on( 'keydown', (evt) => {
            // Figure out if the user started typing, so we can redirect to the input control.
            const key = evt.key;
            const control = (key.length != 1) || (key == " ") || evt.ctrlKey || evt.metaKey || evt.altKey;
            const isBody = $(evt.target).is("body");
            const isPaste = (
                // Windows/linux paste.
                ((key == "v" || key == "V") && evt.ctrlKey) ||
                // Old style shift-insert paste.
                (key == "Insert" && evt.shiftKey) ||
                // OSX paste.
                ((key == "v" || key == "V") && evt.metaKey)
            );

            // Ignore events not to the global body.
            if (!isBody) {
                return;
            }
            // Ignore non-paste control and non-printable keys.
            if (control && !isPaste) {
                return;
            }

            // It is, and it's to the general body since no control is focused.
            $( 'input#message' ).focus();
        });

        $( '#message' ).on('keydown', () => {
            // Let user press "ESC" on the main input box to close search box.
            if(this.inputState.current == "search") {
                this.inputState.setState("empty");
            }
        });

        // Don't allow attachments if they're disabled.
        if (window.maxattachments <= 0) {
            $( 'button.attachment-picker' ).prop('disabled', true);
        } else {
            $( 'button.attachment-picker' ).on( 'click', () => {
                if (this.roomid && this.rooms.has(this.roomid)) {
                    const supportedList: string[] = ["image/*", "text/*"];
                    this.uploadPicker.selectFiles(this.roomid, supportedList.concat(window.mimetypes).join(","));
                }
            });
        }

        $( 'button.message-visibility' ).on( 'click', () => {
            if (event) {
                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();
            }

            if (isPendingMessageSensitive()) {
                $( 'button.message-visibility' ).addClass('message-visible').removeClass('message-sensitive');
            } else {
                $( 'button.message-visibility' ).addClass('message-sensitive').removeClass('message-visible');
            }
        });

        // Ensure we only clear user input on successful message acknowledgement.
        eventBus.on('messageack', (info) => {
            if (info.status == "success") {
                if (info.roomid == this.roomid) {
                    // Now reset the input.
                    $( 'input#message' ).val( '' );
                    $( 'button.message-visibility' ).addClass('message-visible').removeClass('message-sensitive');
                }

                // Always clear the attachment store for the room.
                this.pending.set(info.roomid, {"message": "", "sensitive": false});
                this.awaitingResponse.set(info.roomid, false);

                // Reset our physical controls.
                this.uploadPicker.clearRoom( info.roomid );
            } else {
                // Just unblock the control to try again.
                this.awaitingResponse.set(info.roomid, false);
            }
        });

        // Ensure that we don't let any messages get sent during downtime.
        eventBus.on('connected', () => {
            this.awaitingResponse = new Map();
            this.connected = true;
            this._recalculateSendEnabled();
        });
        eventBus.on('disconnected', () => {
            this.connected = false;
            this._recalculateSendEnabled();
        });

        // Set up the upload picker popover.
        this.uploadPicker = new UploadPicker( eventBus, screenState, '#message' );

        // Ensure that the input box itself doesn't allow messages to be too long.
        $('#message').attr("maxlength", window.maxmessage);
    }

    /**
     * Called when we need to resolve whether to enable or disable the send button. This only needs to
     * happen when moving between a muted and unmuted room, or when disconnecting or reconnecting.
     */
    _recalculateSendEnabled() {
        // Start with the assumption we're unmuted, and only disable if we're disconnected.
        let disabled = !this.connected;

        // Also disable if we're not in any active room.
        if (!this.roomid) {
            disabled = true;
        }

        if (this.myself) {
            if (this.myself.muted) {
                // Always be disabled in this chat, even if we're connected.
                disabled = true;
            }
        }

        $( 'button#sendmessage' ).prop('disabled', disabled);
    }

    /**
     * Called when our parent gets a new update of our own occupant for the current room. Used to figure
     * out if we should always grey out the send button (muted) or not.
     */
    setSelf( selfObj: Occupant | undefined ) {
        this.myself = selfObj;
        this._recalculateSendEnabled();
    }

    /**
     * Called every time the server informs us that preferences were updated, as well as once every
     * connection success or reconnect. We use this to handle any redrawing on a visible upload picker.
     */
    setPreferences( _preferences: Preferences ) {
        this.uploadPicker.resizeRooms();
    }

    /**
     * Called whenever our parent informs us of an updated room list from the server. The room list
     * is always absolute and includes all relevant rooms that we're in, ordered by last update newest
     * to oldest. We only really care about the room list so we can track info about the currently
     * viewed room. If there was a pending room switch and we hadn't yet loaded rooms, this will
     * trigger that room switch upon loading.
     */
    setRooms( rooms: Room[] ) {
        // Make a copy instead of keeping a reference, so we can safely mutate.
        const newRooms = new Map();
        rooms.forEach((room) => {
            newRooms.set(room.id, room);
        });

        this.rooms = newRooms;
        this.roomsLoaded = true;
    }

    /**
     * Called when the manager informs us that the user has selected a new room, or when a new
     * room has been selected for the user (such as selecting a room after joining it).
     */
    setRoom( roomid: string ) {
        if (this.roomsLoaded) {
            if (roomid != this.roomid) {
                // First, save any old room message.
                if (this.roomid) {
                    this.pending.set(
                        this.roomid,
                        {
                            "message": String($( 'input#message' ).val()),
                            "sensitive": isPendingMessageSensitive(),
                        },
                    );
                    this.uploadPicker.hideRoom( this.roomid );
                }

                // Now, show new room's message.
                const pending = this.pending.get(roomid);
                if (pending !== undefined) {
                    $( 'input#message' ).val(pending.message);
                    if ( pending.sensitive ) {
                        $( 'button.message-visibility' ).addClass('message-sensitive').removeClass('message-visible');
                    } else {
                        $( 'button.message-visibility' ).addClass('message-visible').removeClass('message-sensitive');
                    }
                } else {
                    $( 'input#message' ).val('');
                    $( 'button.message-visibility' ).addClass('message-visible').removeClass('message-sensitive');
                }
                this.uploadPicker.showRoom( roomid );

                // Now, swap to that room.
                if (this.rooms.has(roomid)) {
                    this.roomid = roomid;
                    this._recalculateSendEnabled();
                    $( '#message-actions' ).attr('roomid', roomid);
                }
            }
        }
    }

    /**
     * Called whenever our parent informs us that we've left a room. This can happen when
     * the user chooses to leave a room via the info panel. There is not currently a method
     * for having the server kick a user from a room and update the client, but when that's
     * added our parent will call this function as well.
     */
    closeRoom( roomid: string ) {
        // Nuke pending message since we're closing the room.
        this.pending.set(roomid, {'message': '', 'sensitive': false});
        $( 'button.message-visibility' ).addClass('message-visible').removeClass('message-sensitive');

        this.uploadPicker.clearRoom( roomid );

        if (roomid == this.roomid) {
            this.roomid = "";
            this._recalculateSendEnabled();
            $( '#message-actions' ).attr('roomid', '');
            $( 'input#message' ).val('');
        }
    }
}
