import $ from "jquery";

class ChatDetails {
    constructor( eventBus, inputState ) {
        this.eventBus = eventBus;
        this.inputState = inputState;
        this.room = {};
        this.roomLoaded = false;
        this.icon = "";

        $( '#chatdetails-form' ).on( 'submit', (event) => {
            event.preventDefault();
        });

        $( '#chatdetails-confirm' ).on( 'click', (event) => {
            event.preventDefault();
            $.modal.close();
            this.inputState.setState("empty");

            if (this.roomLoaded) {
                this.eventBus.emit('updateroom', {'roomid': this.room.id, 'details': {
                    'name': $('#chatdetails-name').val(),
                    'topic': $('#chatdetails-topic').val(),
                    'icon': this.icon,
                }});
            }
        });

        $( '#chatdetails-cancel' ).on( 'click', (event) => {
            event.preventDefault();
            $.modal.close();
            this.inputState.setState("empty");
        });

        $( '#chatdetails-iconpicker' ).on( 'change', (event) => {
            const file = event.target.files[0];

            if (file && file.size < 1000000) {
                var fr = new FileReader();
                fr.onload = () => {
                    this.icon = fr.result;
                    $( '#chatdetails-icon' ).attr('src', this.icon);
                };
                fr.readAsDataURL(file);
            }
        });
    }

    display( roomid ) {
        if (this.roomLoaded && this.room.id == roomid) {
            $.modal.close();

            // Make sure we don't accidentally set a previous icon.
            this.icon = "";

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

    setRoom( room ) {
        this.room = room;
        this.roomLoaded = true;
    }

    closeRoom( roomid ) {
        if (this.room.id == roomid) {
            this.room = {};
            this.roomLoaded = false;
        }
    }
}

export { ChatDetails };
