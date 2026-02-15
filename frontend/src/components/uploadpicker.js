import $ from "jquery";
import { flash } from "../utils.js";
import { displayAltTextEditor } from "../modals/alttextmodal.js";

class UploadPicker {
    constructor( eventBus, screenState, textBox ) {
        this.eventBus = eventBus;
        this.screenState = screenState;
        this.textBox = textBox;
        this.room = undefined;
        this.rooms = new Map();

        // Make sure on mobile we hide the picker when moving away from the chat screen.
        screenState.registerStateChangeCallback((newState) => {
            if (newState == "chat") {
                if (this.room) {
                    this.showRoom( this.room );
                }
            } else {
                this._hideRooms();
            }
        }, true);

        // Make sure when transitioning from desktop to mobile or back that we show or
        // hide the picker appropriately.
        eventBus.on("resize", (size) => {
            if (size == "desktop") {
                if (this.room) {
                    this.showRoom( this.room );
                }
            } else {
                if (this.screenState.current == "chat") {
                    if (this.room) {
                        this.showRoom( this.room );
                    }
                } else {
                    this._hideRooms();
                }
            }
        }, true);

        // Handle sizing ourselves to the chat box when the window resizes.
        $(window).resize(() => {
            this.resizeRooms();
        });

        // Handle sizing ourselves to the chat box when the info panel resizes.
        eventBus.on('updateinfo', (_info) => {
            this.resizeRooms();
        }, true);

        $( 'input#message-files' ).on( 'change', (event) => {
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();

            const jqe = $(event.target);
            const files = [...event.target.files];
            const roomid = jqe.attr('roomid');

            this._upload(roomid, files);
        });

        $( this.textBox ).on( 'paste', (event) => {
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();

            const files = [...event.originalEvent.clipboardData.files];
            const roomid = this.room;

            if (roomid && files.length > 0) {
                event.stopPropagation();
                event.stopImmediatePropagation();
                event.preventDefault();

                this._upload(roomid, files);
            }
        });

        $( document ).on('click', 'div.uploadpicker div.delete-container', (event) => {
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();

            const jqe = $(event.currentTarget);
            const parts = jqe.attr('id').split('-');

            if (this.rooms.has(parts[0])) {
                const room = this.rooms.get(parts[0]);
                const idx = parseInt(parts[2]);
                room.files.splice(idx, 1);

                this._drawRoom( parts[0] );
            }
        });

        $( document ).on('click', 'div.uploadpicker div.alt-text-container', (event) => {
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();

            const jqe = $(event.currentTarget);
            const parts = jqe.attr('id').split('-');

            if (this.rooms.has(parts[0])) {
                const room = this.rooms.get(parts[0]);
                const idx = parseInt(parts[2]);

                displayAltTextEditor( room.files[idx].data, room.files[idx].alt_text, (event, alt_text) => {
                    room.files[idx].alt_text = alt_text;

                    if (alt_text) {
                        jqe.addClass('present');
                    } else {
                        jqe.removeClass('present');
                    }
                });
            }
        });

        $( document ).on('click', 'div.uploadpicker div.sensitive-container', (event) => {
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();

            const jqe = $(event.currentTarget);
            const parts = jqe.attr('id').split('-');

            if (this.rooms.has(parts[0])) {
                const room = this.rooms.get(parts[0]);
                const idx = parseInt(parts[2]);

                room.files[idx].sensitive = !room.files[idx].sensitive;

                if (room.files[idx].sensitive) {
                    jqe.find('div.attachment-visibility').addClass('attachment-sensitive').removeClass('attachment-visible');
                } else {
                    jqe.find('div.attachment-visibility').addClass('attachment-visible').removeClass('attachment-sensitive');
                }
            }
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
            const picker = $('<div class="uploadpicker"></div>')
                .attr("style", "display:none;")
                .attr("id", roomid)
                .appendTo('body');
            $('<div class="uploadpicker-container"></div>').appendTo(picker);

            this.rooms.set(roomid, {
                'files': [],
            });
        }

        // If there are files, display the picker.
        this._drawRoom(roomid);

        // Ensure we know what room we're displaying.
        this.room = roomid;
    }

    _upload( roomid, files ) {
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
                            alt_text: '',
                            sensitive: false,
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
            const item = $('<div class="upload"></div>')
                .attr('id', roomid + '-upload-' + idx)
                .appendTo(container);
            $('<img />')
                .attr('src', upload.data)
                .appendTo(item);
            const altcontainer = $('<div />')
                .attr('class', 'alt-text-container' + (upload.alt_text ? " present" : ""))
                .attr('id', roomid + '-alt-' + idx)
                .appendTo(item);
            $('<div />')
                .text('alt')
                .appendTo(altcontainer);
            const sensitivecontainer = $('<div />')
                .attr('class', 'sensitive-container')
                .attr('id', roomid + '-sensitive-' + idx)
                .appendTo(item);
            const visibilityClass = upload.sensitive ? 'attachment-sensitive' : 'attachment-visible';
            $('<div />')
                .attr('class', 'maskable attachment-visibility ' + visibilityClass)
                .appendTo(sensitivecontainer);
            const delcontainer = $('<div />')
                .attr('class', 'delete-container')
                .attr('id', roomid + '-upload-' + idx)
                .appendTo(item);
            $('<div />')
                .attr('class', 'delete maskable')
                .appendTo(delcontainer);
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

    // Hides all known rooms, called when we navigate away from the chat
    // screen on mobile.
    _hideRooms() {
        this.rooms.forEach((_val, roomid) => {
            this.hideRoom(roomid);
        });
    }

    // Repositions all known rooms, called when the window is resized or when
    // the info pane is toggled on desktop. Also called when preferences change
    // because this can change the layout.
    resizeRooms() {
        this.rooms.forEach((_val, roomid) => {
            this._reposition(roomid);
        });
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
