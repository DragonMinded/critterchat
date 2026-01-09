import $ from "jquery";

/**
 * Simple warning modal that pops up displaying the warning text as a paragraph, the
 * confirm and cancel text on a pair of action buttons, and potentially calls the confirm
 * or cancel callback on clicking the relevant button. The user can always close the warning
 * panel without clicking confirm or cancel by clicking outside of the modal or closing it.
 */

export function displayWarning( warningText, confirmText, cancelText, confirmCallback, cancelCallback ) {
    // First, close any existing modal, since there can be only one.
    $.modal.close();

    // Now, set the text up for the modal itself.
    $('#warning-text').html(warningText);
    $('#warning-confirm').text(confirmText);
    $('#warning-cancel').text(cancelText);

    // Now, set up the callbacks for actions.
    $( '#warning-confirm').on( 'click', (event) => {
        event.preventDefault();

        $.modal.close();
        
        if (confirmCallback) {
            confirmCallback(event);
        }
    });

    $( '#warning-cancel').on( 'click', (event) => {
        event.preventDefault();

        $.modal.close();
        
        if (cancelCallback) {
            cancelCallback(event);
        }
    });

    // Finally, display the modal.
    $('#warning-form').modal();
}
