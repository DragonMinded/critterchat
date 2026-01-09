import $ from "jquery";

/**
 * Simple information modal that pops up displaying the info text as a paragraph, the
 * confirm text on an action button, and potentially calls the confirm callback on
 * clicking the confirm button. The user can always close the info panel without clicking
 * confirm by clicking outside of the modal or closing it.
 */
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
