TODO Immediate
==============

 - Don't make hovering disappear the emoji search that's visible.
 - Long-press to pull up hover menu on mobile.
 - Verify reactions work fine on mobile.
 - Better polling thread loop with less CPU usage, need to stop waking up once a second.

TODO For Public Instance
========================

 - Stickers support in some form.
 - Start on backend tests.
 - Private group chat creation UI.
 - Private group chat invite UI.
 - Role groups, for moderators and public room visibility, including auto-join on add to group.

TODO Low Priority
=================

 - Generate a unique URI for all chats and rooms, allow editing for public rooms.
 - Mentioning typeahead should allow searching by display nick as well as username.
 - Support editing your nickname and avatar per-chat (limit to non-DMs).
 - Support arbitrary info fields in profile for links to other services, etc.
 - Allow arbitrary statuses such as "LIVE" with ability to put a link in.
 - Image attachment carousel instead of opening images in new browser tab.
 - Rate limiting on actions, which will eventually be needed.
 - Allow unimportant flash messages to fade away after awhile.
 - Audit DB usage (lots of redundant fetches), add per-request cache to alleviate.
 - Link existing local account with an OAuth provider.
 - Unlink existing local account from an OAuth provider.
 - Better integration with Mastodon OAuth that saves client token and only revalidates when needed.
 - Attachment thumbnails so larger images don't get downloaded on slow connections on display.
