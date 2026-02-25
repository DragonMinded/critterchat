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

    $.fn.getCursorPosition = function() {
        var start = null;
        this.each(function(index, elem) {
            if ('selectionStart' in elem) {
                start = elem.selectionStart;
            }
        });

        return start;
    }


    $.fn.hasScrollBar = function() {
        return this.get(0).scrollHeight > this.get(0).clientHeight;
    }

    $.fn.onHold = function(ms_or_filter, callback_or_ms, maybe_callback) {
        const touchCapable = ('ontouchstart' in window);

        if (maybe_callback) {
            const filter = ms_or_filter;
            const ms = callback_or_ms;
            const callback = maybe_callback;

            this.each(function(index, elem) {
                const state = {"holding": false, "moved": false, "timer": undefined};

                $(elem).on(touchCapable ? 'touchstart' : 'mousedown', filter, (event) => {
                    state.holding = true;
                    state.moved = false;
                    state.timer = setTimeout(() => {
                        // Fire hold if they didn't move.
                        if (state.holding && !state.moved) {
                            callback($(event.target));
                        }

                        state.holding = false;
                        state.moved = false;
                        state.timer = undefined;
                    }, ms);
                });

                $(elem).on(touchCapable ? 'touchend' : 'mouseup', filter, () => {
                    state.holding = false;
                    if (state.timer) {
                        clearTimeout(state.timer);
                        state.timer = undefined;
                    }
                });

                $(elem).on(touchCapable ? 'touchmove' : 'mousemove', filter, () => {
                    state.moved = true;
                    if (state.timer) {
                        clearTimeout(state.timer);
                        state.timer = undefined;
                    }
                });
            });
        } else {
            const ms = ms_or_filter;
            const callback = callback_or_ms;

            this.each(function(index, elem) {
                const state = {"holding": false, "moved": false, "timer": undefined};

                $(elem).on(touchCapable ? 'touchstart' : 'mousedown', () => {
                    state.holding = true;
                    state.moved = false;
                    state.timer = setTimeout(() => {
                        // Fire hold if they didn't move.
                        if (state.holding && !state.moved) {
                            callback($(elem));
                        }

                        state.holding = false;
                        state.moved = false;
                        state.timer = undefined;
                    }, ms);
                });

                $(elem).on(touchCapable ? 'touchend' : 'mouseup', () => {
                    state.holding = false;
                    if (state.timer) {
                        clearTimeout(state.timer);
                        state.timer = undefined;
                    }
                });

                $(elem).on(touchCapable ? 'touchmove' : 'mousemove', () => {
                    state.moved = true;
                    if (state.timer) {
                        clearTimeout(state.timer);
                        state.timer = undefined;
                    }
                });
            });
        }
    }
}
