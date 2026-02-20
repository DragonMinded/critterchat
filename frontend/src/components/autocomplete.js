import $ from "jquery";

export function autocomplete(state, selector, items) {
    var displayed = false;
    var handled = false;
    var hovering = false;
    var displaying = [];
    var displayingAdditional = false;

    // Sort our items.
    items = items.toSorted((a, b) => a.text.localeCompare(b.text));

    // Register a callback for controlling global state.
    state.registerStateChangeCallback(function(newState) {
        if (newState == "search") {
            if (displayed) {
                hide();
            }
        }
    });

    $(selector).on('keydown', function(event) {
        handled = false;
        hovering = false;

        if(!displayed) {
            return;
        }

        if(state.current == "search") {
            return;
        }

        const pos = $(selector).getCursorPosition();
        if (pos === null) {
            return;
        }

        // Are we closing the menu?
        if(event.key == "Escape") {
            // Close menu.
            hide();
            handled = true;
            event.preventDefault();
            return false;
        }

        // Is this a menu movement?
        if(event.key == "ArrowUp" || event.key == "ArrowDown") {
            if (event.key == "ArrowUp") {
                cursorup();
            } else {
                cursordown();
            }

            // Don't move the cursor
            handled = true;
            event.preventDefault();
            return false;
        }

        // Is this a menu selection?
        if(event.key == "Enter" || event.key == "Tab") {
            var choice = cursorselection();
            selectOption(choice);

            // Don't send a message or move the cursor.
            handled = true;
            event.preventDefault();
            return false;
        }
    });

    $(selector).on('keyup focus click', function() {
        if (handled) {
            handled = false;
            return;
        }

        if(state.current == "search") {
            return;
        }

        const pos = $(selector).getCursorPosition();
        if (pos === null) {
            hide();
            return;
        }

        // Figure out if we have anything to display.
        var word = "";
        var text = $(selector).val();
        var curpos = pos;

        while(curpos > 0) {
            if(text[curpos - 1].trim() === '') {
                break;
            }
            curpos --;
        }

        while(curpos < text.length) {
            if(text[curpos].trim() === '') {
                break;
            }

            word += text[curpos];
            curpos ++;
        }

        // Show if we are @ing somebody, or if we have at least 2 characters matching an emote.
        if((word.startsWith(":") && !word.endsWith(":") && word.length > 2) || word.startsWith('@'))
        {
            word = word.toLowerCase();

            // First, give us our exact matches.
            var matches = items.filter(function(item) {
                return item.text.toLowerCase().startsWith(word);
            });

            // Now, look up any partial matches if we're doing emoji lookup.
            var noColonPrefix = word.substring(1);
            var partials = (word.startsWith(":") && !word.endsWith(":") && noColonPrefix.length > 0) ? items.filter(function(item) {
                // First, ignore anything that isn't an emoji.
                if (!item.text.startsWith(":") || !item.text.endsWith(":")) {
                    return false;
                }

                // Now, partial match.
                var wordBit = item.text.substring(1, item.text.length - 1).toLowerCase();
                return wordBit.includes(noColonPrefix);
            }) : [];

            // Finally, remove from partials anything that was in the matches list.
            partials = partials.filter(function(partial) {
                return !matches.includes(partial);
            });

            // And now, concatenate so they take lower precedence.
            matches = matches.concat(partials);

            if (matches.length > 0)
            {
                show(matches.slice(0, 10), matches.length > 10);
                return;
            }
        }

        hide();
    });

    $(selector).on('focusout', function() {
        if (!hovering) {
            hide();
        }
    });

    $(window).resize(function() {
        if (displayed) {
            show(displaying, displayingAdditional);
        }
    });

    function selectOption(choice) {
        const pos = $(selector).getCursorPosition();
        if (pos === null) {
            return;
        }

        // Figure out if we have anything to display.
        var text = $(selector).val();
        var curpos = pos;
        var curstart = 0;
        var curend = 0;

        while(curpos > 0) {
            if(text[curpos - 1].trim() === '') {
                break;
            }
            curpos --;
        }
        curstart = curpos;

        while(curpos < text.length) {
            if(text[curpos].trim() === '') {
                break;
            }

            curpos ++;
        }
        curend = curpos;

        if (choice) {
            // Update text with choice, close menu.
            const newval = text.slice(0, curstart) + choice + text.slice(curend);
            $(selector).val(newval);
            $(selector).setCursorPosition(curstart + choice.length);
            hide();
        }
    }

    function hide() {
        displayed = false;
        hovering = false;

        // Broadcast that we're closed.
        if(state.current == "typeahead") {
            state.setState("empty");
        }

        $('div.autocomplete').remove();
    }

    function show(items, additional) {
        if ($('div.autocomplete').length != 0) {
            $('div.autocomplete').remove();
        }

        // Broadcast that we're open.
        state.setState("typeahead");

        // Construct element
        displayed = true;
        displaying = items;
        displayingAdditional = additional;

        $('<div class="autocomplete"></div>').appendTo('body');

        items.forEach(function(item, i) {
            var text = item.text;
            if(text.startsWith('@')) {
                // Display nick as just the preview.
                $( '<div class="autocomplete-element"></div>' )
                    .attr("idx", i)
                    .attr("id", "autocomplete-element-" + i)
                    .html("&nbsp;" + item.preview + "&nbsp;(" + text + ")")
                    .appendTo('div.autocomplete');
            } else {
                // Display emoji/emote as the preview and the text to insert.
                $( '<div class="autocomplete-element"></div>' )
                    .attr("idx", i)
                    .attr("id", "autocomplete-element-" + i)
                    .html("&nbsp;" + item.preview + "&nbsp;" + text)
                    .appendTo('div.autocomplete');
            }

            // Clickable/hoverable selector.
            $("#autocomplete-element-" + i).click(function() {
                var newIdx = parseInt($(this).attr("idx"));
                selectOption(cursorText(newIdx));
            });
            $("#autocomplete-element-" + i).hover(function() {
                var newIdx = parseInt($(this).attr("idx"));
                var idx = parseInt($('div.autocomplete-element.selected').attr("idx"));

                if (idx != newIdx) {
                    // Select new element.
                    var elements = $('div.autocomplete-element');
                    $(elements[idx]).removeClass('selected');
                    $(elements[newIdx]).addClass('selected');
                }

                hovering = true;
            }, function() {
                hovering = false;
            });
        });

        if( additional ) {
            $('<div class="autocomplete-additional">...</div>').appendTo('div.autocomplete');
        }

        cursordown();

        // Position it!
        const offset = $(selector).offset();
        const width = $(selector).outerWidth();
        var height = 0;
        $('div.autocomplete-element').each(function() {
            height += $(this).height();
        });
        $('div.autocomplete-additional').each(function() {
            height += $(this).height();
        });

        $('div.autocomplete').offset({top: offset.top - (height + 2), left:offset.left});
        $('div.autocomplete').width(width - 2);
        $('div.autocomplete').height(height);
    }

    function cursorup() {
        // Try to move cursor up.
        var element = $('div.autocomplete-element.selected');
        if (element.length != 0) {
            element.removeClass('selected');
            element.prev().addClass('selected');
        }

        // Just select the last element if we looped around or have no selection.
        element = $('div.autocomplete-element.selected');
        if (element.length == 0) {
            var elements = $('div.autocomplete-element');
            $(elements[elements.length - 1]).addClass('selected');
        }
    }

    function cursordown() {
        // Try to move cursor down.
        var element = $('div.autocomplete-element.selected');
        if (element.length != 0) {
            element.removeClass('selected');
            element.next().addClass('selected');
        }

        // Just select the last element if we looped around or have no selection.
        element = $('div.autocomplete-element.selected');
        if (element.length == 0) {
            var elements = $('div.autocomplete-element');
            $(elements[0]).addClass('selected');
        }
    }

    function cursorselection() {
        var idx = parseInt($('div.autocomplete-element.selected').attr("idx"));
        return cursorText(idx);
    }

    function cursorText(idx) {
        var text = displaying[idx].text;
        return text;
    }

    function update(newitems) {
        items = newitems.toSorted((a, b) => a.text.localeCompare(b.text));
    }

    return update;
}
