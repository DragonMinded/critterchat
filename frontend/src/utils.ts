import $ from "jquery";

const entityMap: {[index: string]:string} = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
  '`': '&#x60;',
  '=': '&#x3D;',
  '/': '&#x2F;',
};

const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// These are provided by the backend when it renders out the HTML we're part of, and then we keep
// them up-to-date when custom emotes get added or removed from the instance.
declare global {
    interface Window {
        emotes: any;
        emojis: any;
    }
}

/**
 * Given a string, escape all HTML within that string by converting any unsafe characters to their
 * HTML equivalent, and then convert all known emoji and emotes to the correct <img> tag pointing to
 * the asset which should be displayed.
 */
function escapeHtml(str: string): string {
    str = String(str);
        str = str.replace(/[&<>"'`=/]/g, function (s: string): string {
        return entityMap[s]!;
    });
    Object.keys(window.emojis).forEach(function(emoji) {
        str = str.replaceAll(emoji, window.emojis[emoji]);
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
function formatTime(ts: number, showseconds?: boolean, twentyfour?: boolean): string {
    const date = new Date(ts * 1000);
    let hours = date.getHours();
    let ampm = "";
    if (!twentyfour) {
        if (hours == 24) { hours = 0; }

        ampm = hours >= 12 ? " pm" : " am";

        if (hours > 12) { hours -= 12; }
        if (hours < 1) { hours += 12; }
    }
    const minutes = "0" + date.getMinutes();
    const seconds = "0" + date.getSeconds();
    const formattedTime = hours + ':' + minutes.substr(-2) + (showseconds ? ':' + seconds.substr(-2) : '') + ampm;
    return formattedTime;
}

/**
 * Given a unix timestamp, formats the date as human-readable, ignoring the time within the day.
 */
function formatDate(ts: number): string {
    const date = new Date(ts * 1000);
    const month = months[date.getMonth()];
    const day = date.getDate();
    const year = date.getFullYear();
    const formattedDate = month + " " + day + ", " + year;
    return formattedDate;
}

/**
 * Given a unix timestamp, formats the date and time it represents as a human-readable string.
 */
function formatDateTime(ts: number): string {
    return formatDate( ts ) + " @ " + formatTime( ts );
}

/*
 * Given a DOM element, calculates the integer scroll top of a given component. Useful for
 * scrolling back to an element after a full redraw as well as understanding whether the user
 * is at the top or bottom of a scroll area.
 */
function scrollTop(obj: any): number {
    // Sometimes the chrome/firefox calculation of scrollTopMax is off by one
    return Math.floor(obj.scrollTop) + 1;
}

/*
 * Given a DOM element, calculates the maximum scroll top of a given component.
 */
function scrollTopMax(obj: any): number {
    return obj.scrollHeight - obj.clientHeight;
}

/**
 * Given a DOM element, returns true if that element is visible within the viewport that it
 * resides in, or false if it is out of view usually via scrolling.
 */
function isInViewport(el: any): boolean {
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
function flashHook(): void {
    // Ensure that all visible flashes can be closed.
    $( 'ul.errors li button' ).off();
    $( 'ul.errors li button' ).on('click', function(event: any) {
        event.preventDefault();
        const id = $( this ).attr('pid');
        $( 'ul.errors li#' + id ).remove();
        flashHook();
    });

    // Ensures that the flash container is behind other clickable elements if there is nothing to click.
    if ($( 'ul.errors' ).children().length == 0) {
        $( 'ul.errors' ).hide();
    } else {
        $( 'ul.errors' ).show();
    }
};

declare global {
    interface Window { nonce: number; }
}

/**
 * Displays a new flash message at the top, below all existing displayed flash messages. Also ensures
 * that the message itself can be closed by clicking the [x] button on the right hand side.
 */
function flash(type: string, message: string): void {
    const ts = Date.now();
    const nonce = window.nonce || 0;
    window.nonce = nonce + 1;

    let html = '<li class="' + type + '" id="flash' + ts + '' + nonce + '">';
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
function getSelectionText(): string {
    let text = "";

    if (window.getSelection) {
        text = (window.getSelection() || "").toString();
    } else {
        // @ts-ignore TS2551 this is for legacy browser support.
        const selection = document.selection;
        if (selection && selection.type != "Control") {
            text = selection.createRange().text;
        }
    }

    return text;
}

/**
 * Given a haystack to search through and a needle to search, this returns true if the haystack contains
 * that needle standalone. By standalone, this means surrounded on both sides by a whitespace character
 * or the start/end of the message.
 */
function containsStandaloneText(haystack: string, needle: string): boolean {
    needle = needle.toLowerCase();

    let pos = 0;
    while (pos <= (haystack.length - needle.length)) {
        if (pos > 0) {
            const beforeChar = haystack.substring(pos - 1, pos);
            if (
                beforeChar != " " &&
                beforeChar != "\t" &&
                beforeChar != "(" &&
                beforeChar != "[" &&
                beforeChar != "{" &&
                beforeChar != ">" &&
                beforeChar != ";" &&
                beforeChar != "'" &&
                beforeChar != '"'
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
                afterChar != "." &&
                afterChar != "&" &&
                afterChar != "'" &&
                afterChar != '"'
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
function highlightStandaloneText(haystack: string, needle: string, before: string, after: string): string {
    if( haystack.length < needle.length ) {
        return haystack;
    }
    needle = needle.toLowerCase();
    if (!haystack.toLowerCase().includes(needle)) {
        return haystack;
    }

    let pos = 0;
    while (pos <= (haystack.length - needle.length)) {
        if (pos > 0) {
            const beforeChar = haystack.substring(pos - 1, pos);
            if (
                beforeChar != " " &&
                beforeChar != "\t" &&
                beforeChar != "(" &&
                beforeChar != "[" &&
                beforeChar != "{" &&
                beforeChar != ">" &&
                beforeChar != ";" &&
                beforeChar != "'" &&
                beforeChar != '"'
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
                afterChar != "." &&
                afterChar != "&" &&
                afterChar != "'" &&
                afterChar != '"'
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

/**
 * Search through a control and all its parents, trying to find a parent that matches
 * these properties. Note that any of these properties can be undefined, but not all.
 */
function findElement(elem: any, tag: string, prop?: string, hasClass?: string ): any {
    let jqe = $(elem);
    tag = tag.toLowerCase();

    while (true) {
        // If the element doesn't even have a tag name, we've exhausted our search.
        const tagName = jqe.prop('tagName');
        if (!tagName) {
            return undefined;
        }

        // If we ran into a html tag we've exhausted our search.
        const lowerTagName = tagName.toLowerCase();
        if (lowerTagName == "html") {
            return undefined;
        }

        // Now, if the tag doesn't match, this isn't our element.
        if (tag != lowerTagName) {
            jqe = jqe.parent();
            continue;
        }

        // Now, if the prop is set and we don't have this prop, it isn't our element.
        if (prop && !jqe.attr(prop)) {
            jqe = jqe.parent();
            continue;
        }

        // Now, if the class is set and we don't have this class, it isn't our element.
        if (hasClass && !jqe.hasClass(hasClass)) {
            jqe = jqe.parent();
            continue;
        }

        // We found our match!
        return jqe;
    }
}

/**
 * Given an absolute or relative file path (unix or windows), get the extension, or
 * the word "file" if there is no valid extension.
 */
function getExt(path: string): string {
    const parts = path.includes("\\") ? path.split("\\") : path.split("/");
    const filename = parts[parts.length - 1]!;
    const fileparts = filename.split(".");
    fileparts.shift();

    // Form an extension to display, or display generic if empty.
    let fullext = fileparts.length > 0 ? fileparts.join(".") : "file";
    if (fullext.includes(".")) {
        const lower = fullext.toLowerCase();

        if (!lower.startsWith("tar.")) {
            // This isn't one of our exceptions.
            fullext = fileparts[fileparts.length - 1]!;
        }
    }

    return fullext;
}

/**
 * Given an absolute or relative file path (unix or windows), get the filename
 * itself without the path.
 */
function getFilename(path: string): string {
    const parts = path.includes("\\") ? path.split("\\") : path.split("/");
    return parts[parts.length - 1]!;
}

/**
 * Given a mimetype, returns true if the mimetype represents what a person
 * considers text, or false otherwise. This means that the document is
 * renderable as plain text, so things that are in the application namespace
 * but are actually just text still count.
 */
function isText(mt: string): boolean {
    mt = mt.toLowerCase();
    if (mt.startsWith("text/")) {
        return true;
    }
    if (mt == "application/json") {
        return true;
    }
    if (mt == "application/javascript") {
        return true;
    }
    if (mt == "application/xml") {
        return true;
    }

    return false;
}

/**
 * Given an extension and a mimetype, return the mask image that represents
 * that file for an attachment thumbnail.
 */
function getAttachmentImage(ext: string, mt: string): string {
    mt = mt.toLowerCase();

    if (isText(mt) || mt == "application/pdf") {
        return "file-text";
    }
    if (mt.startsWith("audio/")) {
        return "file-audio";
    }
    if (mt.startsWith("video/")) {
        return "file-video";
    }
    if (mt.startsWith("image/")) {
        return "file-image";
    }
    return "file-binary";
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
    findElement,
    isText,
    getExt,
    getFilename,
    getAttachmentImage,
};
