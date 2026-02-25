import $ from "jquery";
import { escapeHtml } from "../utils.js";
import { emojisearch } from "../components/emojisearch.js";

const searchOptions = {
    attributes: function( _icon, _variant ) {
        return {
            loading: "lazy",
            width: "72",
            height: "72",
        };
    },
};

class Reactions {
    constructor( eventBus, screenState, inputState, callback ) {
        this.eventBus = eventBus;
        this.screenState = screenState;
        this.inputState = inputState;
        this.callback = callback;
        this.hovering = false;
        this.id = undefined;
        this.search = emojisearch(this.inputState, '.custom-reaction', $('<div />'), this._getEmojiSearchOptions(), (value) => {
            if (this.id && value) {
                this.callback(this.id, 'reaction', value);
            }
        });

        $( document ).on( 'click', 'div.reactions-popover button.reaction', (event) => {
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();

            var value = undefined;
            var target = $(event.target);

            while (target.prop("tagName").toLowerCase() != "html") {
                value = target.attr('data');
                if (value) {
                    break;
                }

                target = target.parent();
            }

            if (this.id && value) {
                this.callback(this.id, 'reaction', value);
            }
        });
    }

    _getEmojiSearchOptions() {
        const emojiSearchOptions = [];
        for (const [key, value] of Object.entries(window.emojis)) {
            emojiSearchOptions.push(
                {text: key, type: "emoji", preview: twemoji.parse(value, {...twemojiOptions, ...searchOptions})}
            );
        }
        for (const [key, value] of Object.entries(window.emotes)) {
            const src = "src=\"" + value.uri + "\"";
            const dims = "width=\"" + value.dimensions[0] + "\" height=\"" + value.dimensions[1] + "\"";

            emojiSearchOptions.push(
                {text: key, type: "emote", preview: "<img class=\"emoji-preview\" " + src + " " + dims + " loading=\"lazy\" />"}
            );
        }

        return emojiSearchOptions;
    }

    show( id ) {
        if (this.id) {
            // Kill any visible reaction box.
            $("div.reactions-popover").off();
            $("div.reactions-popover").remove();
        }
        if (this.id != id) {
            this.search.hide();
        }

        this.id = id;
        this.hovering = false;

        // Create a container.
        const container = $('<div class="reactions-popover"></div>');
        const controls = $('<div class="reactions-controls"></div>').appendTo(container);

        // Add the defaults.
        window.reactionsdefaults.forEach((value) => {
            const real = ":" + value + ":";
            const html = escapeHtml(real);
            $('<button class="reaction"></button>')
                .html(html)
                .attr('data', real)
                .appendTo(controls);

            $('<div class="separator" />').appendTo(controls);
        });

        // Add the custom selector.
        const search = $('<button class="custom-reaction"></button>').appendTo(controls);
        $('<div class="maskable search-svg"></div>').appendTo(search);

        // Attach it to the message itself.
        var parentBox = $('div.conversation div.message#' + this.id);
        if (!parentBox.html()) {
            parentBox = $('div.conversation div.attachments#' + this.id);
        }
        container.appendTo(parentBox);

        // Figure out the height of our container, and move it accordingly.
        const height = container.outerHeight();
        container.css('top', '-' + (height - 5) + 'px');

        // Hook the search button to the emoji popover.
        this.search.reparent(controls);

        // Stop the reactions box from disappearing when we're hovering over it
        // in any capacity.
        container.on("mouseenter", () => {
            this.hovering = true;
        });

        container.on("mouseleave", () => {
            if (this.hovering && !this.id) {
                // We should have closed, so do that now.
                this.hovering = false;
                this.hide();
            }
        });
    }

    hide() {
        if (!this.hovering) {
            // Kill any visible reaction box.
            $("div.reactions-popover").off();
            $("div.reactions-popover").remove();
            this.search.hide();
        }

        // Stop tracking what message we're paying attention to.
        this.id = undefined;
    }
}

export { Reactions };
