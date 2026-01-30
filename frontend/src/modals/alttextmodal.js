import $ from "jquery";

/**
 * Simple modal that pops up when you click the "ALT" button to add or edit alt text for a
 * pending attachment upload.
 */

export function displayAltTextEditor( image, existing, applyCallback ) {
    // First, close any existing modal, since there can be only one.
    $.modal.close();

    // Now, set the text up for the modal itself.
    $('#alt-text-image').attr('src', image);
    $('#alt-text-text').val(existing || "");

    // Now, set up the callbacks for actions.
    $('#alt-text-confirm').on( 'click', (event) => {
        event.preventDefault();

        $.modal.close();

        if (applyCallback) {
            applyCallback(event, $('#alt-text-text').val());
        }
    });

    $('#alt-text-cancel').on( 'click', (event) => {
        event.preventDefault();

        $.modal.close();
    });

    // Finally, display the modal.
    $('#alt-text-form').modal();
}
