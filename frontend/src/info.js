import $ from "jquery";

class Info {
    constructor( eventBus ) {
        this.eventBus = eventBus;
        this.roomid = "";
        this.occupants = [];
        this.lastSettings = {};
        this.lastSettingsLoaded = false;

        $( '#infotoggle' ).on( 'click', (event) => {
            event.preventDefault();

            if ($('div.container > div.info').hasClass('hidden')) {
                $('div.container > div.info').removeClass('hidden');
                this.lastSettings.info = "shown";
            } else {
                $('div.container > div.info').addClass('hidden');
                this.lastSettings.info = "hidden";
            }

            this.eventBus.emit('info', this.lastSettings.info);
        });

        $( '#leave-room' ).on( 'click', (event) => {
            event.preventDefault();

            this.eventBus.emit('leaveroom', $( '#leave-room' ).attr('roomid'));
        });
    }

    setLastSettings( settings ) {
        this.lastSettings = settings;
        this.lastSettingsLoaded = true;

        if (this.lastSettings.info == "shown") {
            $('div.container > div.info').removeClass('hidden');
        } else {
            $('div.container > div.info').addClass('hidden');
        }
    }

    setRoom( roomid ) {
        if (roomid != this.roomid) {
            this.occupants = [];
            this.roomid = roomid;

            $('div.info > div.occupants').empty();
            $( '#leave-room' ).attr('roomid', roomid);
        }
    }

    closeRoom( roomid ) {
        if (roomid == this.roomid) {
            this.occupants = [];
            this.roomid = "";

            $('div.info > div.occupants').empty();
            $( '#leave-room' ).attr('roomid', '');
        }
    }
}

export { Info };
