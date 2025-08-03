import $ from "jquery";

class EditProfile {
    constructor( eventBus, inputState ) {
        this.eventBus = eventBus;
        this.inputState = inputState;
        this.profile = {};
        this.profileLoaded = false;
        this.icon = "";

        $( '#editprofile-form' ).on( 'submit', (event) => {
            event.preventDefault();
        });

        $( '#editprofile-confirm' ).on( 'click', (event) => {
            event.preventDefault();
            $.modal.close();
            this.inputState.setState("empty");

            if (this.profileLoaded) {
                this.eventBus.emit('updateprofile', {'details': {
                    'name': $('#editprofile-name').val().substring(0, 255),
                    'icon': this.icon,
                }});
            }
        });

        $( '#editprofile-cancel' ).on( 'click', (event) => {
            event.preventDefault();
            $.modal.close();
            this.inputState.setState("empty");
        });

        $( '#editprofile-iconpicker' ).on( 'change', (event) => {
            const file = event.target.files[0];

            if (file && file.size < 128 * 1024) {
                var fr = new FileReader();
                fr.onload = () => {
                    this.icon = fr.result;
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

            $("#editprofile-name-label").text("nickname");
            $("#editprofile-name").attr('placeholder', 'Type a custom nickname...');

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
