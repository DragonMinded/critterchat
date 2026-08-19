TODO Immediate
==============

 - Fix topic getting cut off on mobile on some long channel names.
 - Need a setting for low-motion to disable motion by default, need to swap to low motion icons when setting present, need to swap to low motion thumb even on animated gifs and such when setting present. Need to also swap server icons and custom emotes as well, but these might require a reload.

TODO Low Priority
=================

 - Replace \<div\> with \<button\> on emoji picker popover interactable elements.
 - Replace \<div\> with \<button\> on attachment picker popover interactable elements.
 - Generate a unique URI for all conversations and rooms, allow editing for public rooms.
 - Mentioning typeahead should allow searching by display nick as well as username.
 - Support editing your nickname and avatar per-room (limit to non-DMs).
 - Support arbitrary info fields in profile for links to other services, etc.
 - Allow arbitrary statuses such as "LIVE" with ability to put a link in.
 - Image attachment carousel instead of opening images in new browser tab.
 - Rate limiting on actions, which will eventually be needed.
 - Allow unimportant flash messages to fade away after awhile.
 - Audit DB usage (lots of redundant fetches), add per-request cache to alleviate.
 - Link existing local account with an OAuth provider.
 - Unlink existing local account from an OAuth provider.
 - Better integration with Mastodon OAuth that saves client token and only revalidates when needed.
 - Role groups, for moderators and public room visibility, including auto-join on add to group.
 - Better autocomplete that lets you scroll down past the first 10 entries.
 - When server selects a room for you, ensure that the menu on the left scrolls to make that room visible.
 - Proper history integration for mobile so browser back action works the same as back button.
