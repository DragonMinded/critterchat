var entityMap = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
  '/': '&#x2F;',
  '`': '&#x60;',
  '=': '&#x3D;'
};

var escapeHtml = function( str ) {
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

var formatTime = function( ts, showseconds, twentyfour ) {
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
    return formattedTime
}

// Calculate the integer scroll top of a given component.
var scrollTop = function( obj ) {
    // Sometimes the chrome/firefox calculation of scrollTopMax is off by one
    return Math.floor(obj.scrollTop) + 1;
}

// Calculate the maximum scroll top of a given component.
var scrollTopMax = function( obj ) {
    return obj.scrollHeight - obj.clientHeight;
}

export { escapeHtml, formatTime, scrollTop, scrollTopMax };
