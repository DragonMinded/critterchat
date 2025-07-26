import $ from "jquery";

export function displayInfo( infoText, confirmText, confirmCallback ) {
    // First, close any existing modal, since there can be only one.
    $.modal.close();

    // Now, set the text up for the modal itself.
    $('#info-text').html(infoText);
    $('#info-confirm').text(confirmText);

    // Now, set up the callbacks for actions.
    $( '#info-confirm').on( 'click', (event) => {
        event.preventDefault();

        $.modal.close();

        if (confirmCallback) {
            confirmCallback(event);
        }
    });

    // Finally, display the modal.
    $('#info-form').modal();
}
