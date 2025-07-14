import $ from "jquery";

export function displayWarning( warningText, confirmText, cancelText, confirmCallback, cancelCallback ) {
    // First, close any existing modal, since there can be only one.
    $.modal.close();

    // Now, set the text up for the modal itself.
    $('#warning-text').text(warningText);
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
