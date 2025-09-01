import $ from "jquery";

class EditPreferences {
    constructor( eventBus, inputState ) {
        this.eventBus = eventBus;
        this.inputState = inputState;
        this.preferences = {};
        this.preferencesLoaded = false;

        $( '#editpreferences-form' ).on( 'submit', (event) => {
            event.preventDefault();
        });

        $( '#editpreferences-confirm' ).on( 'click', (event) => {
            event.preventDefault();
            $.modal.close();
            this.inputState.setState("empty");

            if (this.preferencesLoaded) {
                this.eventBus.emit('updatepreferences', {
                    'title_notifs': $('#editpreferences-title-notifications').is(":checked"),
                });
            }
        });

        $( '#editpreferences-cancel' ).on( 'click', (event) => {
            event.preventDefault();
            $.modal.close();
            this.inputState.setState("empty");
        });
    }

    display() {
        if (this.preferencesLoaded) {
            $.modal.close();

            $('#editpreferences-form').modal();
            $('#editpreferences-title-notifications').prop('checked', this.preferences.title_notifs);
        }
    }

    setPreferences( preferences ) {
        this.preferences = preferences;
        this.preferencesLoaded = true;
    }
}

export { EditPreferences };
