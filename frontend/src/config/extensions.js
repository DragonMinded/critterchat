import $ from "jquery";

/**
 * Hook function that adds any custom jQuery handlers which this code provides.
 * Called by the entrypoint in chat.js before even defining a document onReady
 * handler, so that any use of jQuery across the client can use these functions.
 */
export function hook() {
    $.fn.setCursorPosition = function(pos) {
        this.each(function(index, elem) {
            if (elem.setSelectionRange) {
                elem.setSelectionRange(pos, pos);
            } else if (elem.createTextRange) {
                var range = elem.createTextRange();
                range.collapse(true);
                range.moveEnd('character', pos);
                range.moveStart('character', pos);
                range.select();
            }
        });
        return this;
    };

    $.fn.hasScrollBar = function() {
        return this.get(0).scrollHeight > this.get(0).clientHeight;
    }
}
