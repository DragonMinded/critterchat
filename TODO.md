TODO Immediate
==============

 - Double-reaction popover when abusing the hoverfix state change.
 - Replace <div> with <button> on menu panels for accessibility and tab completion.
 - Replace <div> with <button> on back buttons for accessibility and tab completion.
 - Replace <div> with <button> on instance info for accessibility and tab completion.
 - Aria hidden on menu images, info images, instance info image.
 - Aria description for back buttons.
 - Show highlight on reaction buttons when tabbing between them.
 - Reaction popover shows up sometimes on window switch on mobile.

TODO For Public Instance
========================

 - Stickers support in some form.

TODO Low Priority
=================

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
 - Attachment thumbnails so larger images don't get downloaded on slow connections on display.
 - Role groups, for moderators and public room visibility, including auto-join on add to group.
 - Better autocomplete that lets you scroll down past the first 10 entries.
 - When server selects a room for you, ensure that the menu on the left scrolls to make that room visible.
 - Proper history integration for mobile so browser back action works the same as back button.
 - Flesh out tests for attachment, mastodon and room data subsystems, add SQLite as a database option.
 - Low-motion option for those who are sensitive to motion.
