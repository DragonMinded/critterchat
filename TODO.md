TODO Immediate
==============

 - Fix modal popover not allowing scrollable content when sizing down.
 - Combine like messages together with a preference to do so.
 - Remove message fetch limit when fetching newer messages in "get_room_updates".
 - When reconnecting, request actions from all rooms, not just active one, or we might miss badges.
 - Move notification event generation and reconnect support out of message.js and into manager.js.
 - Include last action on 'roomlist' when requesting or when sending in event loop, use that to prime monitoring for events on reconnect.
 - Prime event monitoring with 'chatactions' responses.

TODO Short Term
===============

 - Source code documentation and comments, use JS feature for private methods and attributes.
 - Notification indicator on back button in chat and info on mobile.
 - Notification indicator by changing favicon to a notifications version.
 - Start on profile view to look at a person's profile.
 - Support editing your nickname and avatar per-chat (limit to public rooms).
 - Rework attachments to properly identify mime type and preserve extensions.

TODO Low Priority
=================

 - Generate a unique URI for all chats and rooms, allow editing for public rooms.
 - Better feedback when choosing a sound or avatar that won't be accepted.
 - URL for public chats to link directly as an invite.
 - Chat info name and topic should support emoji autocomplete and emoji search.
 - Mentioning typeahead should allow searching by display nick as well as username.
 - Support creating an account flow with ability to disable instance-side and setting for auto-activate or moderator activate.
