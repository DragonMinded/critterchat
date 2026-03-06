TODO Immediate
==============

 - Preference for auto-accept group invites.
 - Preference for allowing room invites, preference for allowing group invites.
 - Allow uninviting to room (revoke invite action).
 - Show invited rooms on search results (allow join that way), ensure deduplicating from rooms you can see.

TODO For Public Instance
========================

 - Stickers support in some form.
 - Accessibility pass.

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
 - Role groups, for moderators and public room visibility, including auto-join on add to group.
 - Better autocomplete that lets you scroll down past the first 10 entries.
 - When server selects a room for you, ensure that the menu on the left scrolls to make that room visible.
