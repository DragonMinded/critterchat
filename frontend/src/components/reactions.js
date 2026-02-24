import $ from "jquery";
import { escapeHtml } from "../utils.js";

// TODO: Move this to backend config file.
const defaults = [
    ":thumbs_up:",
    ":thumbs_down:",
    ":heart:",
];

class Reactions {
    constructor( eventBus, screenState, callback ) {
        this.eventBus = eventBus;
        this.screenState = screenState;
        this.callback = callback;
        this.hovering = false;
        this.id = undefined;

        $( document ).on( 'click', 'div.reactions-popover div.reaction', (event) => {
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
                callback(this.id, 'reaction', value);
            }
        });
    }

    show( id ) {
        if (this.id) {
            // Kill any visible reaction box.
            $("div.reactions-popover").off();
            $("div.reactions-popover").remove();
        }

        this.id = id;

        // Create a container.
        const container = $('<div class="reactions-popover"></div>');
        const controls = $('<div class="reactions-controls"></div>').appendTo(container);

        // Add the defaults.
        defaults.forEach((value) => {
            const html = escapeHtml(value);
            $('<div class="reaction"></div>')
                .html(html)
                .attr('data', value)
                .appendTo(controls);
        });

        // Attach it to the message itself.
        var parentBox = $('div.conversation div.message#' + this.id);
        if (!parentBox.html()) {
            parentBox = $('div.conversation div.attachments#' + this.id);
        }
        container.appendTo(parentBox);

        // Figure out the height of our container, and move it accordingly.
        const height = container.outerHeight();
        container.css('top', '-' + (height - 5) + 'px');

        // Stop the reactions box from disappearing when we're hovering over it
        // in any capacity.
        container.on("mouseenter", () => {
            this.hovering = true;
        });

        container.on("mouseleave", () => {
            if (this.hovering && !this.id) {
                // We should have closed, so do that now.
                $("div.reactions-popover").off();
                $("div.reactions-popover").remove();
            }

            this.hovering = false;
        });
    }

    hide( id ) {
        if (id == this.id) {
            if (!this.hovering) {
                // Kill any visible reaction box.
                $("div.reactions-popover").off();
                $("div.reactions-popover").remove();
            }

            // Stop tracking what message we're paying attention to.
            this.id = undefined;
        }
    }
}

export { Reactions };
