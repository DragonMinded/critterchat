import $ from "jquery";
import { findElement } from "../utils.js"

function getCursorStart(element) {
    var el = $(element).get(0);
    if ('selectionStart' in el) {
        return el.selectionStart;
    }

    return null;
}

function getCursorEnd(element) {
    var el = $(element).get(0);
    if ('selectionEnd' in el) {
        return el.selectionEnd;
    }

    return null;
}

export class EmojiSearch {
    constructor(state, button, control, items, callback) {
        this.state = state;
        this.button = button;
        this.control = control;
        this.callback = callback;

        this.displayed = false;
        this._lastCategory = "";

        // Create our picker, hide it.
        this._container = $('<div class="emojisearch"></div>')
            .attr("style", "display:none;")
            .appendTo('body');
        const inner = $('<div class="emojisearch-container"></div>').appendTo(this._container);
        $('<div class="emojisearch-typeahead"></div>')
            .html('<input type="text" id="emojisearch-text" placeholder="search" />')
            .appendTo(inner);
        $('<div class="emojisearch-categories"></div>')
            .appendTo(inner);
        $('<div class="emojisearch-content"></div>')
            .appendTo(inner);

        // Initial hooks.
        this._populate(items);
        this._hook();

        // Register a callback for controlling global state.
        state.registerStateChangeCallback((newState) => {
            // Allow ourselves to be hidden if an external system wants us closed.
            if (newState == "empty") {
                if (this.displayed) {
                    this.hide();
                }
            }
        });

        // Handle searching for an emoji.
        this._container.find("#emojisearch-text").on('input', (event) => {
            var searchInput = $(event.target).val().toLowerCase();

            if (searchInput == "") {
                // Erased search, put us back to normal.
                this._container.find("div.emojisearch-category").each((i, elem) => {
                    var elemCat = $(elem).attr("category");
                    if (elemCat == this._lastCategory) {
                        $(elem).click();
                    }
                });
                return;
            }

            // Make sure all categories are highlighted.
            this._container.find("div.emojisearch-category").each((i, elem) => {
                if (!$(elem).hasClass("selected")) {
                    $(elem).addClass("selected");
                }
            });

            this._container.find("div.emojisearch-element").each((i, elem) => {
                var elemText = $(elem).attr("text").toLowerCase();
                if (elemText.includes(searchInput)) {
                    $(elem).show();
                } else {
                    $(elem).hide();
                }
            });
        });

        // Handle toggling the search open or closed.
        $(this.button).on('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();

            if (this.displayed) {
                this.hide();
            } else {
                this._show();
            }
        });
        $(this.button).addClass('hooked');

        this._container.find("#emojisearch-text").on('keydown', (event) => {
            // Are we closing the search?
            if(event.key == "Escape") {
                this.hide();
                $(this.control).focus();
            }
        });

        // Handle sizing ourselves to the chat box when the window resizes.
        $(window).resize(() => {
            if (this.displayed) {
                this._show();
            }
        });
    }

    _populate(entries) {
        if (!this._container) {
            return;
        }

        // Filter out categories.
        var categories = {};
        Object.keys(window.emojicategories).forEach((category) => {
            categories[category] = [];

            Object.keys(window.emojicategories[category]).forEach((subcategory) => {
                window.emojicategories[category][subcategory].forEach((emoji) => {
                    categories[category].push(":" + emoji.toLowerCase() + ":");
                });
            });
        });

        // Add custom emoji if they exist.
        entries.forEach((entry) => {
            if (entry.type != "emote") {
                return;
            }

            if (!categories.hasOwnProperty("Custom")) {
                categories["Custom"] = []
            }

            categories["Custom"].push(entry.text.toLowerCase());
        });

        // Find icons for categories.
        var catkeys = {};
        Object.keys(categories).forEach((category) => {
            catkeys[categories[category][0]] = "";
        });

        // Make a mapping of the emojis and emotes.
        var emojimapping = {}
        entries.forEach((entry) => {
            var text = entry.text.toLowerCase();
            if (catkeys.hasOwnProperty(text)) {
                // We really need to rethink how this control is populated, we should probably
                // be sending a preview src URI instead of a DOM element. Oh well, future FIXME.
                catkeys[text] = entry.preview.replace('loading="lazy"', '');
            }
            emojimapping[text] = entry;
        });

        // Nuke any existing categories we had.
        this._container.find("div.emojisearch-category").remove();
        this._container.find("div.emojisearch-element").remove();

        var emojisearchCategories = this._container.find('div.emojisearch-categories');
        var emojisearchContent = this._container.find('div.emojisearch-content');

        // Actually render the categories.
        Object.keys(categories).forEach((category) => {
            var first = categories[category][0];
            var preview = catkeys[first];

            emojisearchCategories.append(
                $('<div class="emojisearch-category"></div>')
                    .attr("category", category)
                    .html(preview)
            );

            var catList = categories[category];
            if (category == "Custom") {
                // Make sure we have sorted emoji.
                catList = catList.toSorted((a, b) => emojimapping[a].text.localeCompare(emojimapping[b].text));
            }

            var appendList = [];
            catList.forEach((entry) => {
                if (emojimapping.hasOwnProperty(entry)) {
                    appendList.push(
                        $('<div class="emojisearch-element"></div>')
                            .attr("text", emojimapping[entry].text)
                            .attr("category", category)
                            .html(emojimapping[entry].preview)
                    );
                }
            });

            emojisearchContent.append(appendList);
        });
    }

    _hook() {
        if (!this._container) {
            return;
        }

        // Set up category selection.
        this._container.find("div.emojisearch-category").click((event) => {
            // Don't allow selection when search is happening.
            var searchInput = this._container.find("#emojisearch-text").val();

            if (searchInput != "") {
                return;
            }

            const target = findElement(event.target, "div", "category", "emojisearch-category");
            const category = target.attr("category");
            this._lastCategory = category;

            this._container.find("div.emojisearch-category").each((i, elem) => {
                var elemCat = $(elem).attr("category");
                $(elem).removeClass("selected");
                if (elemCat == category) {
                    $(elem).addClass("selected");
                }
            });

            this._container.find("div.emojisearch-element").each((i, elem) => {
                var elemCat = $(elem).attr("category");
                if (elemCat == category) {
                    $(elem).show();
                } else {
                    $(elem).hide();
                }
            });

            // Make sure to scroll to the top of the visible list.
            this._container.find("div.emojisearch-content").scrollTop(0);
        });

        // Select first emoji category.
        this._container.find("div.emojisearch-category")[0].click();

        // Handle selecting an emoji.
        this._container.find(".emojisearch-element").click((event) => {
            const target = findElement(event.target, "div", "text", "emojisearch-element");
            var emoji = target.attr("text");

            if (this.callback) {
                this.hide();
                this.callback(emoji, $(this.control));
            } else {
                var textcontrol = $(this.control);

                var start = getCursorStart(textcontrol);
                var end = getCursorEnd(textcontrol);
                if (end === null) {
                    end = start;
                }

                if (start !== null && end !== null) {
                    var val = textcontrol.val();

                    const newval = val.slice(0, start) + emoji + val.slice(end);
                    textcontrol.val(newval);
                    textcontrol.setCursorPosition(start + emoji.length);
                }

                this.hide();
                textcontrol.focus();
            }
        });
    }

    _show() {
        if (!this._container) {
            return;
        }

        // First, close any other search elements.
        this.state.setState("empty");

        // Construct element
        this.displayed = true;
        this._container.show();

        // Broadcast that we're open.
        this.state.setState("search");

        // Position ourselves!
        const offset = $(this.control).offset();
        var width = $(this.control).outerWidth() - 2;
        const height = this._container.height();
        var left = offset.left;
        var start = offset.top - (height + 2);

        const minWidth = 250;
        const minPadding = 5;
        if (this.callback && (width < minWidth)) {
            // We're popping over a custom reaction picker, don't be too small.
            const delta = minWidth - width;

            width += delta;
            left -= delta;
        }

        if (this.callback && start < minPadding) {
            // We're popping over a reaction picker and the top is cut off.
            start = offset.top + $(this.control).outerHeight();
        }

        if (this.callback && left < minPadding) {
            // We're popping over a reaction picker and the left is cut off.
            left += (minPadding - left);
        }

        this._container.offset({top: start, left: left});
        this._container.width(width);

        // Make sure search typeahead is focused.
        this._container.find('#emojisearch-text').val("");
        this._container.find('#emojisearch-text').focus();

        // Make sure the emoji button stays highlighted.
        if (!$(this.button).hasClass("opened")) {
            $(this.button).addClass("opened");
        }
    }

    hide() {
        if (!this._container || !this.displayed) {
            return;
        }

        this.displayed = false;

        // Broadcast that we're closed.
        if(this.state.current == "search") {
            this.state.setState("empty");
        }

        // Hide our top level.
        this._container.hide();

        // Also make sure search is cleared.
        var searchVal = this._container.find("#emojisearch-text").val();
        if (searchVal != "") {
            this._container.find("#emojisearch-text").val("");

            // Erased search, put us back to normal.
            this._container.find("div.emojisearch-category").each((i, elem) => {
                var elemCat = $(elem).attr("category");
                if (elemCat == this._lastCategory) {
                    $(elem).click();
                }
            });
        }

        // Also make sure the emoji button isn't highlighted anymore.
        if ($(this.button).hasClass("opened")) {
            $(this.button).removeClass("opened");
        }
    }

    // Provide a callback so that our caller can inform us of new emoji.
    update( newitems ) {
        if (!this._container) {
            return;
        }

        this._populate(newitems);
        this._hook();
    }

    // Provide a way to kill this control.
    destroy() {
        this._hide();

        if (this._container) {
            this._container.remove();
            this._container = undefined;
        }
    }

    // Provide a way to reparent this control.
    reparent( newbutton_or_control, newcontrol ) {
        $(this.button).removeClass('hooked');
        $(this.button).off();

        if ( newcontrol ) {
            this.button = newbutton_or_control;
            this.control = newcontrol;
        } else {
            this.control = newbutton_or_control;
        }

        if (this.displayed) {
            this._show();
        }

        $(this.button).on('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();

            if (this.displayed) {
                this.hide();
            } else {
                this._show();
            }
        });
        $(this.button).addClass('hooked');
    }

    // Provide a way to programatically pop this up attached to a control.
    show( newbutton_or_control, newcontrol ) {
        if (this.displayed) {
            this.hide();
        }

        if (newbutton_or_control || newcontrol) {
            this.reparent( newbutton_or_control, newcontrol );
        }

        this._show();
    }

    // Provide a way to ask if a button is already bound to this control.
    bound( button ) {
        return $(button).hasClass('hooked');
    }
}
