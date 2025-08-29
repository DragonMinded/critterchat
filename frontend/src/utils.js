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

const escapeHtml = function( str ) {
    str = String(str);
        str = str.replace(/[&<>"'`=/]/g, function (s) {
        return entityMap[s];
    });
    Object.keys(emojis).forEach(function(emoji) {
        str = str.replaceAll(emoji, emojis[emoji]);
    });
    str = twemoji.parse(str, twemojiOptions);
    Object.keys(emotes).forEach(function(emote) {
        str = str.replaceAll(emote, "<img src='" + emotes[emote] + "' class='emote' alt='" + emote + "' />");
    });
    return str;
}

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

const formatDate = function( ts ) {
    var date = new Date(ts * 1000);
    var month = months[date.getMonth()];
    var day = date.getDate();
    var year = date.getFullYear();
    var formattedDate = month + " " + day + ", " + year;
    return formattedDate;
}

const formatDateTime = function( ts ) {
    return formatDate( ts ) + " @ " + formatTime( ts );
}

// Calculate the integer scroll top of a given component.
const scrollTop = function( obj ) {
    // Sometimes the chrome/firefox calculation of scrollTopMax is off by one
    return Math.floor(obj.scrollTop) + 1;
}

// Calculate the maximum scroll top of a given component.
const scrollTopMax = function( obj ) {
    return obj.scrollHeight - obj.clientHeight;
}

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

const flashHook = function() {
    $( 'ul.errors li button' ).on('click', function(event) {
        event.preventDefault();
        const id = $( this ).attr('pid');
        $( 'ul.errors li#' + id ).remove();
    });
};

const flash = function( type, message ) {
    const ts = Date.now();
    const nonce = window.nonce || 0;
    window.nonce = nonce + 1;

    var html = '<li class="' + type + '" id="flash' + ts + '' + nonce + '">';
    html    += '  <div>' + message + '</div>';
    html    += '  <button pid="flash' + ts + '' + nonce + '" class="close ' + type + '">&#10060;</button>';
    html    += '</li>';

    $( 'ul.errors' ).append(html);
    flashHook();
}

const getSelectionText = function() {
    let text = "";

    if (window.getSelection) {
        text = window.getSelection().toString();
    } else if (document.selection && document.selection.type != "Control") {
        text = document.selection.createRange().text;
    }

    return text;
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
};
