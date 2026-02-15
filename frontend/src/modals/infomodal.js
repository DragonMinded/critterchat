import $ from "jquery";

/**
 * Simple information modal that pops up displaying the info text as a paragraph, the
 * confirm text on an action button, and potentially calls the confirm callback on
 * clicking the confirm button. The user can always close the info panel without clicking
 * confirm by clicking outside of the modal or closing it.
 */
export function displayInfo( infoText, confirmText, confirmCallback, sticky ) {
    // First, close any existing modal, since there can be only one.
    $.modal.close();

    // Unhook any previous instance hooks that didn't get unhooked if we were closed by dismissing.
    $( '#info-confirm').off();

    // Now, set the text up for the modal itself.
    $('#info-text').html(infoText);
    $('#info-confirm').text(confirmText);

    // Now, set up the callbacks for actions.
    $( '#info-confirm').on( 'click', (event) => {
        event.preventDefault();

        // Unhook ourselves so we don't have dangling callbacks.
        $( '#info-confirm').off();

        $.modal.close();

        if (confirmCallback) {
            confirmCallback(event);
        }
    });

    // Finally, display the modal.
    if (sticky) {
        // Only let something be sticky if we have a confirm callback, intentionally.
        $('#info-form').modal({
            escapeClose: false,
            clickClose: false,
            showClose: false,
        });
    } else {
        $('#info-form').modal();
    }
}
