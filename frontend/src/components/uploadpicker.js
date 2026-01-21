import $ from "jquery";
import { flash } from "../utils.js";

class UploadPicker {
    constructor( eventBus, inputState, textBox ) {
        this.eventBus = eventBus;
        this.inputState = inputState;
        this.textBox = textBox;
        this.rooms = new Map();

        inputState.registerStateChangeCallback(function(_newState) {
            // TODO: Need to possibly close ourselves here.
        });

        $( 'input#message-files' ).on( 'change', (event) => {
            const jqe = $(event.target);
            const files = [...event.target.files];
            const roomid = jqe.attr('roomid');

            // First, display the picker window, so we can ensure we have the
            // tracking variable.
            this.showRoom( roomid );

            // Allow tracking files with JS's callback hell.
            const room = this.rooms.get(roomid);
            var existing = room.files.length;

            files.forEach((file) => {
                if (file.size < window.maxattachmentsize * 1024) {
                    if (existing < window.maxattachments) {
                        existing = existing + 1;

                        var fr = new FileReader();
                        fr.onload = () => {
                            room.files.push({
                                filename: file.name,
                                data: fr.result,
                            });

                            this._drawRoom( roomid );
                        };

                        fr.readAsDataURL(file);
                    } else {
                        flash('warning', 'Too many attachments for upload!');
                    }
                } else {
                    flash('warning', 'File is too large for attachment upload!');
                }
            });
        });
    }

    selectFiles( roomid, mimetype ) {
        $('input#message-files').attr('accept', mimetype);
        $('input#message-files').attr('roomid', roomid);
        $('input#message-files').click();
    }

    files( roomid ) {
        if (this.rooms.has(roomid)) {
            return this.rooms.get(roomid).files;
        } else {
            return [];
        }
    }

    // Show the upload picker for a given room. Possibly shows an existing room's
    // picker, or a new one if the room has been changed.
    showRoom( roomid ) {
        // Ensure the component exists.
        if (!this.rooms.has(roomid)) {
            $('<div class="uploadpicker"></div>')
                .attr("style", "display:none;")
                .attr("id", roomid)
                .appendTo('body');
            $('<div class="uploadpicker-container"></div>').appendTo('div.uploadpicker#' + roomid);

            this.rooms.set(roomid, {
                'files': [],
            });
        }

        // If there are files, display the picker.
        this._drawRoom(roomid);
    }

    // Called whenever we reflow the textbox, so it always hovers above the message box.
    _reposition( roomid ) {
        const offset = $(this.textBox).offset();
        const width = $(this.textBox).outerWidth();
        const height = $('div.uploadpicker#' + roomid).height();

        $('div.uploadpicker#' + roomid).offset({top: offset.top - (height), left:offset.left});
        $('div.uploadpicker#' + roomid).width(width);
    }

    // Called after we get a new file added or removed from our list.
    _drawRoom( roomid ) {
        const container = $('div.uploadpicker#' + roomid + ' div.uploadpicker-container');

        container.empty();

        const room = this.rooms.get(roomid);
        room.files.forEach((upload, idx) => {
            $('<div class="upload"></div>')
                .attr('id', 'upload' + idx)
                .appendTo(container);
            $('<img />')
                .attr('height', 75)
                .attr('src', upload.data)
                .appendTo('div.upload#upload' + idx);
        });

        if (room.files.length > 0) {
            $('div.uploadpicker#' + roomid).show();
            this._reposition(roomid);
        } else {
            $('div.uploadpicker#' + roomid).hide();
        }
    }

    // Hide the display of the requested room.
    hideRoom( roomid ) {
        $('div.uploadpicker#' + roomid).hide();
    }

    // Clear (and hide) the upload picker for a given room.
    clearRoom( roomid ) {
        // First, hide the display if it's present.
        this.hideRoom(roomid);

        // Now, delete any files that were pending for the room.
        if (this.rooms.has(roomid)) {
            const room = this.rooms.get(roomid);
            room.files = [];
        }
    }
}

export { UploadPicker };
