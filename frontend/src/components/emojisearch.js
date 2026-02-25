import $ from "jquery";

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

export function emojisearch(state, button, control, items, callback) {
    var displayed = false;
    var lastCategory = "";
    var container = undefined;

    function create() {
        // Create our picker, hide it.
        container = $('<div class="emojisearch"></div>')
            .attr("style", "display:none;")
            .appendTo('body');
        const inner = $('<div class="emojisearch-container"></div>').appendTo(container);
        $('<div class="emojisearch-typeahead"></div>')
            .html('<input type="text" id="emojisearch-text" placeholder="search" />')
            .appendTo(inner);
        $('<div class="emojisearch-categories"></div>')
            .appendTo(inner);
        $('<div class="emojisearch-content"></div>')
            .appendTo(inner);
    }

    function populate(entries) {
        if (!container) {
            return;
        }

        // Filter out categories.
        var categories = {};
        Object.keys(window.emojicategories).forEach(function(category) {
            categories[category] = [];

            Object.keys(window.emojicategories[category]).forEach(function(subcategory) {
                window.emojicategories[category][subcategory].forEach(function(emoji) {
                    categories[category].push(":" + emoji.toLowerCase() + ":");
                });
            });
        });

        // Add custom emoji if they exist.
        entries.forEach(function(entry) {
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
        Object.keys(categories).forEach(function(category) {
            catkeys[categories[category][0]] = "";
        });

        // Make a mapping of the emojis and emotes.
        var emojimapping = {}
        entries.forEach(function(entry) {
            var text = entry.text.toLowerCase();
            if (catkeys.hasOwnProperty(text)) {
                // We really need to rethink how this control is populated, we should probably
                // be sending a preview src URI instead of a DOM element. Oh well, future FIXME.
                catkeys[text] = entry.preview.replace('loading="lazy"', '');
            }
            emojimapping[text] = entry;
        });

        // Nuke any existing categories we had.
        container.find("div.emojisearch-category").remove();
        container.find("div.emojisearch-element").remove();

        var emojisearchCategories = container.find('div.emojisearch-categories');
        var emojisearchContent = container.find('div.emojisearch-content');

        // Actually render the categories.
        Object.keys(categories).forEach(function(category) {
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
            catList.forEach(function(entry) {
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

    function hook() {
        if (!container) {
            return;
        }

        // Set up category selection.
        container.find("div.emojisearch-category").click(function() {
            // Don't allow selection when search is happening.
            var searchInput = container.find("#emojisearch-text").val();

            if (searchInput != "") {
                return;
            }

            var category = $(this).attr("category");
            lastCategory = category;

            container.find("div.emojisearch-category").each(function(i, elem) {
                var elemCat = $(elem).attr("category");
                $(elem).removeClass("selected");
                if (elemCat == category) {
                    $(elem).addClass("selected");
                }
            });

            container.find("div.emojisearch-element").each(function(i, elem) {
                var elemCat = $(elem).attr("category");
                if (elemCat == category) {
                    $(elem).show();
                } else {
                    $(elem).hide();
                }
            });

            // Make sure to scroll to the top of the visible list.
            container.find("div.emojisearch-content").scrollTop(0);
        });

        // Select first emoji category.
        container.find("div.emojisearch-category")[0].click();

        // Handle selecting an emoji.
        container.find(".emojisearch-element").click(function() {
            var emoji = $(this).attr("text");

            if (callback) {
                hide();
                callback(emoji);
            } else {
                var textcontrol = $(control);

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

                hide();
                textcontrol.focus();
            }
        });
    }

    function show() {
        if (!container) {
            return;
        }

        // First, close any other search elements.
        state.setState("empty");

        // Construct element
        displayed = true;
        container.show();

        // Broadcast that we're open.
        state.setState("search");

        // Position ourselves!
        const offset = $(control).offset();
        var width = $(control).outerWidth() - 2;
        const height = container.height();
        var left = offset.left;
        var start = offset.top - (height + 2);

        const minWidth = 250;
        if (callback && (width < minWidth)) {
            // We're popping over a custom reaction picker, don't be too small.
            const delta = minWidth - width;

            width += delta;
            left -= delta;
        }

        if (callback && start < 0) {
            // We're popping over a reactin picker and the top is cut off.
            start = offset.top + $(control).outerHeight();
        }

        container.offset({top: start, left:left});
        container.width(width);

        // Make sure search typeahead is focused.
        container.find('#emojisearch-text').val("");
        container.find('#emojisearch-text').focus();

        // Make sure the emoji button stays highlighted.
        if (!$(button).hasClass("opened")) {
            $(button).addClass("opened");
        }
    }

    function hide() {
        if (!container || !displayed) {
            return;
        }

        displayed = false;

        // Broadcast that we're closed.
        if(state.current == "search") {
            state.setState("empty");
        }

        // Hide our top level.
        container.hide();

        // Also make sure search is cleared.
        var searchVal = container.find("#emojisearch-text").val();
        if (searchVal != "") {
            container.find("#emojisearch-text").val("");

            // Erased search, put us back to normal.
            container.find("div.emojisearch-category").each(function(i, elem) {
                var elemCat = $(elem).attr("category");
                if (elemCat == lastCategory) {
                    $(elem).click();
                }
            });
        }

        // Also make sure the emoji button isn't highlighted anymore.
        if ($(button).hasClass("opened")) {
            $(button).removeClass("opened");
        }
    }

    // Initial creation.
    create();
    populate(items);
    hook();

    // Register a callback for controlling global state.
    state.registerStateChangeCallback(function(newState) {
        // Allow ourselves to be hidden if an external system wants us closed.
        if (newState == "empty") {
            if (displayed) {
                hide();
            }
        }
    });

    // Handle searching for an emoji.
    container.find("#emojisearch-text").on('input', function() {
        var searchInput = $(this).val().toLowerCase();

        if (searchInput == "") {
            // Erased search, put us back to normal.
            container.find("div.emojisearch-category").each(function(i, elem) {
                var elemCat = $(elem).attr("category");
                if (elemCat == lastCategory) {
                    $(elem).click();
                }
            });
            return;
        }

        // Make sure all categories are highlighted.
        container.find("div.emojisearch-category").each(function(i, elem) {
            if (!$(elem).hasClass("selected")) {
                $(elem).addClass("selected");
            }
        });

        container.find("div.emojisearch-element").each(function(i, elem) {
            var elemText = $(elem).attr("text").toLowerCase();
            if (elemText.includes(searchInput)) {
                $(elem).show();
            } else {
                $(elem).hide();
            }
        });
    });

    // Handle toggling the search open or closed.
    $(button).on('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();

        if (displayed) {
            hide();
        } else {
            show();
        }
    });

    container.find("#emojisearch-text").on('keydown', function(event) {
        // Are we closing the search?
        if(event.key == "Escape") {
            hide();
            $(control).focus();
        }
    });

    // Handle sizing ourselves to the chat box when the window resizes.
    $(window).resize(function() {
        if (displayed) {
            show();
        }
    });

    // Provide a callback so that our caller can inform us of new emoji.
    function update(newitems) {
        if (!container) {
            return;
        }

        populate(newitems);
        hook();
    }

    // Provide a way to kill this control.
    function destroy() {
        hide();

        if (container) {
            container.remove();
            container = undefined;
        }
    }

    // Provide a way to reparent this control.
    function reparent(newcontrol) {
        control = newcontrol;
        if (displayed) {
            show();
        }

        $(button).off();
        $(button).on('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();

            if (displayed) {
                hide();
            } else {
                show();
            }
        });
    }

    return {'reparent': reparent, 'update': update, 'hide': hide, 'destroy': destroy};
}
