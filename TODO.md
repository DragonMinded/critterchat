TODO Immediate
==============

 - Dividing line for title is a little bit too subtle.
 - Profile copy setting for Mastodon OAuth integration.
 - Attachment alt text wrong for multi-pictures, seems to copy the last picture's text.
 - Send base URL domain with set-cookie and update config to document upload domain should be a subdomain.

TODO For Public Instance
========================

 - Stickers support in some form.
 - Emote/emoji reactions to messages.
 - Start on backend tests.

TODO Low Priority
=================

 - Generate a unique URI for all chats and rooms, allow editing for public rooms.
 - Chat info name and topic should support emoji autocomplete and emoji search.
 - Mentioning typeahead should allow searching by display nick as well as username.
 - Support editing your nickname and avatar per-chat (limit to public rooms).
 - Support config-based image attachment disable by setting attachments to 0.
 - Support arbitrary info fields in profile for links to other services, etc.
 - Allow arbitrary statuses such as "LIVE" with ability to put a link in.
 - Image attachment carousel instead of opening images in new browser tab.
 - Rate limiting on actions, which will eventually be needed.
 - Allow unimportant flash messages to fade away after awhile.
 - Audit DB usage (lots of redundant fetches), add per-request cache to alleviate.
 - Link existing local account with an OAuth provider.
 - Unlink existing local account from an OAuth provider.
 - Better integration with Mastodon OAuth that saves client token and only revalidates when needed.
