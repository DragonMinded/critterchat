import $ from "jquery";

class EditProfile {
    constructor( eventBus, inputState ) {
        this.eventBus = eventBus;
        this.inputState = inputState;
        this.profile = {};
        this.profileLoaded = false;
        this.icon = "";
        this.iconDelete = false;

        $( '#editprofile-form' ).on( 'submit', (event) => {
            event.preventDefault();
        });

        $( '#editprofile-confirm' ).on( 'click', (event) => {
            event.preventDefault();
            $.modal.close();
            this.inputState.setState("empty");

            if (this.profileLoaded) {
                this.eventBus.emit('updateprofile', {
                    'name': $('#editprofile-name').val().substring(0, 255),
                    'icon': this.icon,
                    'icon_delete': this.iconDelete,
                });
            }
        });

        $( '#editprofile-cancel' ).on( 'click', (event) => {
            event.preventDefault();
            $.modal.close();
            this.inputState.setState("empty");
        });

        $( '#editprofile-remove-icon' ).on( 'click', (event) => {
            event.preventDefault();
            this.icon = "";
            this.iconDelete = true;

            $( '#editprofile-icon' ).attr('src', window.defavi);
        });

        $( '#editprofile-iconpicker' ).on( 'change', (event) => {
            const file = event.target.files[0];

            if (file && file.size < 128 * 1024) {
                var fr = new FileReader();
                fr.onload = () => {
                    console.log("yeah");
                    this.icon = fr.result;
                    this.iconDelete = false;
                    $( '#editprofile-icon' ).attr('src', this.icon);
                };
                fr.readAsDataURL(file);
            }
        });
    }

    display() {
        if (this.profileLoaded) {
            $.modal.close();

            // Make sure we don't accidentally set a previous icon.
            this.icon = "";
            this.iconDelete = false;

            $('#editprofile-form')[0].reset();
            $('#editprofile-name').val(this.profile.nickname);
            $('#editprofile-icon').attr('src', this.profile.icon);
            $('#editprofile-form').modal();
        }
    }

    setProfile( profile ) {
        // Server sets the nickname field to the username field for easier display,
        // but that means we need to not pretend that our nickname is set to our
        // username if it's not set.
        if (profile.username == profile.nickname) {
            profile.nickname = "";
        }
        this.profile = profile;
        this.profileLoaded = true;
    }
}

export { EditProfile };
