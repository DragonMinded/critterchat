import $ from "jquery";

class ChatDetails {
    constructor( eventBus, inputState ) {
        this.eventBus = eventBus;
        this.inputState = inputState;
        this.room = {};
        this.roomLoaded = false;

        $( '#chatdetails-form' ).on( 'submit', (event) => {
            event.preventDefault();
        });

        $( '#chatdetails-confirm' ).on( 'click', (event) => {
            event.preventDefault();
            $.modal.close();

            if (this.roomLoaded) {
                this.eventBus.emit('updateroom', {'roomid': this.room.id, 'details': {
                    'name': $('#chatdetails-name').val(),
                    'topic': $('#chatdetails-topic').val(),
                }});
            }
        });

        $( '#chatdetails-cancel' ).on( 'click', (event) => {
            event.preventDefault();
            $.modal.close();
        });
    }

    display( roomid ) {
        if (this.roomLoaded && this.room.id == roomid) {
            $.modal.close();

            var photoType = this.room['public'] ? 'room' : 'avatar';
            $('div.chatdetails div.icon').removeClass('avatar').removeClass('room').addClass(photoType);

            var roomType = this.room.type == "chat" ? "chat" : "room";
            $("#chatdetails-name-label").text(roomType + " name");
            $("#chatdetails-name").attr('placeholder', 'Type a custom name for this ' + roomType + '...');
            $("#chatdetails-topic-label").text(roomType + " topic");
            $("#chatdetails-topic").attr('placeholder', 'Type a topic for this ' + roomType + '...');

            $('#chatdetails-name').val(this.room.name);
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
