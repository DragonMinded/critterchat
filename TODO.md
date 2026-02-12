TODO Immediate
==============

 - Unify config files with new options.
 - Fix README section about not running migrations.
 - Don't look up user info for /static/ or /attachments/.
 - Fix not joining any rooms when logging back on and no settings.
 - Need a deauth command for a mastodon instance, can't delete or account links will fail.
 - Welcome message support.

TODO For Public Instance
========================

 - Stickers support in some form.
 - Emote/emoji reactions to messages.
 - Another pass over PROTOCOL.md.

TODO Low Priority
=================

 - Generate a unique URI for all chats and rooms, allow editing for public rooms.
 - Chat info name and topic should support emoji autocomplete and emoji search.
 - Mentioning typeahead should allow searching by display nick as well as username.
 - Support editing your nickname and avatar per-chat (limit to public rooms).
 - Allow config-based image attachment disable.
 - Support arbitrary info fields in profile for links to other services, etc.
 - Allow arbitrary statuses such as "LIVE" with ability to put a link in.
 - Image attachment carousel instead of opening images in new browser tab.
 - Rate limiting on actions, which will eventually be needed.
 - Allow unimportant flash messages to fade away after awhile.
 - Audit DB usage (lots of redundant fetches), add per-request cache to alleviate.
 - Link existing local account with an OAuth provider.
 - Unlink existing local account from an OAuth provider.
