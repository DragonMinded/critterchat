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

var escapehtml = function(str) {
  str = String(str);
  str = str.replace(/[&<>"'`=\/]/g, function (s) {
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


export { escapehtml };
