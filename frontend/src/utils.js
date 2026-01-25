import $ from "jquery";

const entityMap = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
  '/': '&#x2F;',
  '`': '&#x60;',
  '=': '&#x3D;'
};

const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/**
 * Given a string, escape all HTML within that string by converting any unsafe characters to their
 * HTML equivalent, and then convert all known emoji and emotes to the correct <img> tag pointing to
 * the asset which should be displayed.
 */
const escapeHtml = function( str ) {
    str = String(str);
        str = str.replace(/[&<>"'`=/]/g, function (s) {
        return entityMap[s];
    });
    Object.keys(emojis).forEach(function(emoji) {
        str = str.replaceAll(emoji, emojis[emoji]);
    });
    str = twemoji.parse(str, twemojiOptions);
    Object.keys(window.emotes).forEach(function(emote) {
        const src = "src=\"" + window.emotes[emote].uri + "\"";
        const dims = "width=\"" + window.emotes[emote].dimensions[0] + "\" height=\"" + window.emotes[emote].dimensions[1] + "\"";

        str = str.replaceAll(
            emote,
            "<img " + src + " " + dims + " class=\"emote\" alt=\"" + emote + "\" title=\"" + emote + "\" />"
        );
    });
    return str;
}

/**
 * Given a unix timestamp, formats the time as human-readable within the day. Allows for 24 hour
 * and 12 hour display as well as displaying or hiding seconds.
 */
const formatTime = function( ts, showseconds, twentyfour ) {
    var date = new Date(ts * 1000);
    var hours = date.getHours();
    var ampm = "";
    if (!twentyfour) {
        if (hours == 24) { hours = 0; }

        ampm = hours >= 12 ? " pm" : " am";

        if (hours > 12) { hours -= 12; }
        if (hours < 1) { hours += 12; }
    }
    var minutes = "0" + date.getMinutes();
    var seconds = "0" + date.getSeconds();
    var formattedTime = hours + ':' + minutes.substr(-2) + (showseconds ? ':' + seconds.substr(-2) : '') + ampm;
    return formattedTime;
}

/**
 * Given a unix timestamp, formats the date as human-readable, ignoring the time within the day.
 */
const formatDate = function( ts ) {
    var date = new Date(ts * 1000);
    var month = months[date.getMonth()];
    var day = date.getDate();
    var year = date.getFullYear();
    var formattedDate = month + " " + day + ", " + year;
    return formattedDate;
}

/**
 * Given a unix timestamp, formats the date and time it represents as a human-readable string.
 */
const formatDateTime = function( ts ) {
    return formatDate( ts ) + " @ " + formatTime( ts );
}

/*
 * Given a DOM element, calculates the integer scroll top of a given component. Useful for
 * scrolling back to an element after a full redraw as well as understanding whether the user
 * is at the top or bottom of a scroll area.
 */
const scrollTop = function( obj ) {
    // Sometimes the chrome/firefox calculation of scrollTopMax is off by one
    return Math.floor(obj.scrollTop) + 1;
}

/*
 * Given a DOM element, calculates the maximum scroll top of a given component.
 */
const scrollTopMax = function( obj ) {
    return obj.scrollHeight - obj.clientHeight;
}

/**
 * Given a DOM element, returns true if that element is visible within the viewport that it
 * resides in, or false if it is out of view usually via scrolling.
 */
const isInViewport = function( el ) {
    if (el) {
        el = el[0];
        if (el) {
            const rect = el.getBoundingClientRect();
            return (
                rect.top >= 0 &&
                rect.left >= 0 &&
                rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
                rect.right <= (window.innerWidth || document.documentElement.clientWidth)
            );
        } else {
            return false;
        }
    } else {
        return false;
    }
};

/**
 * Finds all displayed flash messages on the top of the screen and ensures that their close button
 * is bound to a jQuery handler to remove the message from the DOM. Normally, when a new flash
 * message is drawn this is done automatically. However, the rendered HTML template that we attach
 * to can also add flash messages of its own such as a successful login acknowledgement. This goes
 * through and ensures that those are also closeable.
 */
const flashHook = function() {
    $( 'ul.errors li button' ).on('click', function(event) {
        event.preventDefault();
        const id = $( this ).attr('pid');
        $( 'ul.errors li#' + id ).remove();
    });
};

/**
 * Displays a new flash message at the top, below all existing displayed flash messages. Also ensures
 * that the message itself can be closed by clicking the [x] button on the right hand side.
 */
const flash = function( type, message ) {
    const ts = Date.now();
    const nonce = window.nonce || 0;
    window.nonce = nonce + 1;

    var html = '<li class="' + type + '" id="flash' + ts + '' + nonce + '">';
    html    += '  <div class="flash-message">' + message + '</div>';
    html    += '  <button pid="flash' + ts + '' + nonce + '" class="close ' + type + '">';
    html    += '    <div class="maskable close-svg"></div>';
    html    += '</button>';
    html    += '</li>';

    $( 'ul.errors' ).append(html);
    flashHook();
}

/**
 * Grabs the selection text for the window. Essentially, this grabs whatever text the user has highlighted
 * on the page by double or triple-clicking, or by click-dragging the text.
 */
const getSelectionText = function() {
    let text = "";

    if (window.getSelection) {
        text = window.getSelection().toString();
    } else if (document.selection && document.selection.type != "Control") {
        text = document.selection.createRange().text;
    }

    return text;
}

/**
 * Given a haystack to search through and a needle to search, this returns true if the haystack contains
 * that needle standalone. By standalone, this means surrounded on both sides by a whitespace character
 * or the start/end of the message.
 */
const containsStandaloneText = function( haystack, needle ) {
    needle = needle.toLowerCase();

    var pos = 0;
    while (pos <= (haystack.length - needle.length)) {
        if (pos > 0) {
            const beforeChar = haystack.substring(pos - 1, pos);
            if (
                beforeChar != " " &&
                beforeChar != "\t" &&
                beforeChar != "(" &&
                beforeChar != "[" &&
                beforeChar != "{" &&
                beforeChar != ">"
            ) {
                pos ++;
                continue;
            }
        }
        if (pos < (haystack.length - needle.length)) {
            const afterChar = haystack.substring(pos + needle.length, pos + needle.length + 1);
            if (
                afterChar != " " &&
                afterChar != "\t" &&
                afterChar != ")" &&
                afterChar != "]" &&
                afterChar != "}" &&
                afterChar != "<" &&
                afterChar != "!" &&
                afterChar != "?" &&
                afterChar != ";" &&
                afterChar != ":" &&
                afterChar != "," &&
                afterChar != "."
            ) {
                pos ++;
                continue;
            }
        }

        if (haystack.substring(pos, pos + needle.length).toLowerCase() != needle) {
            pos++;
            continue;
        }

        return true;
    }

    return false;
}

/**
 * Given a haystack to search through, a needle to search, and a before and after to surround any found
 * text with, does that surrounding. Note that this has the same rules as the standalone text contains
 * function above, where both sides need to be surrounded by whitespace or the start/end of message.
 */
const highlightStandaloneText = function( haystack, needle, before, after ) {
    if( haystack.length < needle.length ) {
        return haystack;
    }
    needle = needle.toLowerCase();
    if (!haystack.toLowerCase().includes(needle)) {
        return haystack;
    }

    var pos = 0;
    while (pos <= (haystack.length - needle.length)) {
        if (pos > 0) {
            const beforeChar = haystack.substring(pos - 1, pos);
            if (
                beforeChar != " " &&
                beforeChar != "\t" &&
                beforeChar != "(" &&
                beforeChar != "[" &&
                beforeChar != "{" &&
                beforeChar != ">"
            ) {
                pos ++;
                continue;
            }
        }
        if (pos < (haystack.length - needle.length)) {
            const afterChar = haystack.substring(pos + needle.length, pos + needle.length + 1);
            if (
                afterChar != " " &&
                afterChar != "\t" &&
                afterChar != ")" &&
                afterChar != "]" &&
                afterChar != "}" &&
                afterChar != "<" &&
                afterChar != "!" &&
                afterChar != "?" &&
                afterChar != ";" &&
                afterChar != ":" &&
                afterChar != "," &&
                afterChar != "."
            ) {
                pos ++;
                continue;
            }
        }

        if (haystack.substring(pos, pos + needle.length).toLowerCase() != needle) {
            pos++;
            continue;
        }

        haystack = (
            haystack.substring(0, pos) +
            before +
            haystack.substring(pos, pos + needle.length) +
            after +
            haystack.substring(pos + needle.length, haystack.length)
        );

        pos += needle.length + before.length + after.length;
    }

    return haystack;
}


export {
    escapeHtml,
    formatTime,
    formatDate,
    formatDateTime,
    scrollTop,
    scrollTopMax,
    isInViewport,
    flash,
    flashHook,
    getSelectionText,
    containsStandaloneText,
    highlightStandaloneText,
};
