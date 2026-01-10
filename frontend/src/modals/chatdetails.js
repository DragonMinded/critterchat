import $ from "jquery";

/**
 * Handles the chat details popover which is summoned and managed by the info panel
 * and allows the user to modify the room name, topic and custom icon.
 */
class ChatDetails {
    constructor( eventBus, inputState ) {
        this.eventBus = eventBus;
        this.inputState = inputState;
        this.room = {};
        this.roomLoaded = false;
        this.icon = "";
        this.iconDelete = false;

        $( '#chatdetails-form' ).on( 'submit', (event) => {
            event.preventDefault();
        });

        $( '#chatdetails-confirm' ).on( 'click', (event) => {
            event.preventDefault();
            $.modal.close();
            this.inputState.setState("empty");

            if (this.roomLoaded) {
                this.eventBus.emit('updateroom', {'roomid': this.room.id, 'details': {
                    'name': $('#chatdetails-name').val().substring(0, 255),
                    'topic': $('#chatdetails-topic').val().substring(0, 255),
                    'icon': this.icon,
                    'icon_delete': this.iconDelete,
                }});
            }
        });

        $( '#chatdetails-cancel' ).on( 'click', (event) => {
            event.preventDefault();
            $.modal.close();
            this.inputState.setState("empty");
        });

        $( '#chatdetails-remove-icon' ).on( 'click', (event) => {
            event.preventDefault();
            this.icon = "";
            this.iconDelete = true;

            $( '#chatdetails-icon' ).attr('src', this.room['deficon']);
        });

        $( '#chatdetails-iconpicker' ).on( 'change', (event) => {
            const file = event.target.files[0];

            if (file && file.size < 128 * 1024) {
                var fr = new FileReader();
                fr.onload = () => {
                    this.icon = fr.result;
                    this.iconDelete = false;
                    $( '#chatdetails-icon' ).attr('src', this.icon);
                };
                fr.readAsDataURL(file);
            }
        });
    }

    /**
     * Called when our parent component wants us to be displayed on the screen. Causes us to
     * close any existing modal, open the chat details modal, and render the various details
     * for the room onto the DOM by finding the correct elements to update.
     */
    display( roomid ) {
        if (this.roomLoaded && this.room.id == roomid) {
            $.modal.close();

            // Start with a fresh form (clear bad file inputs).
            $('#chatdetails-form')[0].reset()

            // Make sure we don't accidentally set a previous icon.
            this.icon = "";
            this.iconDelete = false;

            var photoType = this.room['public'] ? 'room' : 'avatar';
            $('div.chatdetails div.icon').removeClass('avatar').removeClass('room').addClass(photoType);

            var roomType = this.room.type == "chat" ? "chat" : "room";
            $("#chatdetails-name-label").text(roomType + " name");
            $("#chatdetails-name").attr('placeholder', 'Type a custom name for this ' + roomType + '...');
            $("#chatdetails-topic-label").text(roomType + " topic");
            $("#chatdetails-topic").attr('placeholder', 'Type a topic for this ' + roomType + '...');

            $('#chatdetails-name').val(this.room.customname);
            $('#chatdetails-topic').val(this.room.topic);
            $('#chatdetails-icon').attr('src', this.room.icon);
            $('#chatdetails-form').modal();
        }
    }

    /**
     * Called when our parent informs us that the user has selected a new room, or when a new
     * room has been selected for the user (such as selecting a room after joining it). In either
     * case, all we care about is updating the room's information so we can display it for edit.
     */
    setRoom( room ) {
        this.room = room;
        this.roomLoaded = true;
    }

    /**
     * Called whenever our parent informs us that we've left a room. This can happen when
     * the user chooses to leave a room via the info panel. There is not currently a method
     * for having the server kick a user from a room and update the client, but when that's
     * added our parent will call this function as well.
     */
    closeRoom( roomid ) {
        if (this.room.id == roomid) {
            this.room = {};
            this.roomLoaded = false;
        }
    }
}

export { ChatDetails };
