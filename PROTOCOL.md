# Protocol Documentation

This is an attempt to document the HTTP and websocket protocol provided by CritterChat's backend and used by CritterChat's frontend. This serves two purposes. First, it allows a high-level overview that hopefully sidesteps some new developer ramp-up time. Second, it hopefully aids in alternative clients being developed without them having to reverse-engineer everything from as-built code.

At the high level, communcation between the existing web-based JS client and the backend server is done via [Socket.IO](https://socket.io/) which uses websockets under the hood. Socket.IO presents an event-driven interface which we view as named JSON packets. The various packets, whether they are server or client-originated, what they do, and when you should expect to send or receive them is all documented below. Bulk data transfers such as attachment uploads or downloads are handled using HTTP. This is partially to allow for a CDN or other simple system to handle attachments, and partially due to size limitations of websocket packets.

## Authentication

Authentication is not handled by websockets in CritterChat. Instead, there is a POST method that lives at `/login` accepting browser form data which sets a `SessionID` cookie. In the future, I'd like this endpoint to be versatile enough to accept both form data in the post body for browser-based login and JSON in the post body for alternative clients. For now, the important part of this interaction is the `SessionID` cookie that is sent back to the client which should be present on the websocket connection itself. All websocket requests use this cookie to link the websocket session to a logged-in user. If a session is invalidated for any reason, the server will respond to any request with a `reload` packet instructing the client to reload and redo authentication to get a new `SessionID` cookie.

## Upload Endpoints

Data uploads are handled by a series of upload endpoints which take their data as POST bodies. Note that client requests to these endpoints should include the authentication cooke as this allows us to prevent non-authenticated users from uploading arbitrary attachments. Attachments themselves are uploaded using base64 data URLs due to the need for web-based clients to load and display previews of the attachments before uploading. Depending on their purpose they have different ways of handling attachment data and returning an attachmend ID that the client can then use to refer to an attachment when sending a websocket request. Note that all endpoints return JSON representing the results of the request.

### Icon Upload

This endpoint lives at `/upload/icon` and expects a text/plain POST body containing a data URL that represents the icon being uploaded. The icon must be of a supported type (png, jpg, gif, apng, webp, bmp), must be at most 512x512 in size, and must be square (width and height match). If all of those properties hold, the icon will be stored in a new attachment ID and returned as the `attachmentid` property of the response JSON. If any of these is violated, this will instead return JSON with the `error` property containing a text description of the error. Note that icons are only used for customizing the icon of a room or 1:1 chat.

### Avatar Upload

This endpoint lives at `/upload/avatar`. Note that it has identical expectations and responses as the icon upload. The only difference is that this is used for user avatar customization.

### Notification Sound Upload

This endpoint lives at `/upload/notifications` and expects an application/json POST body containing a `notif_sounds` attribute. That `notif_sounds` attribute should point at a JSON object whose keys are the notification being updated and the values are string data URLs that represent the notification sound being uploaded. The sound must be of a supported audio type that FFMPEG can convert and will be converted to an mp3 for broad browser support. Upon successful conversion and storage in the attachment system, a JSON response will be returned containing the same `notif_sounds` attribute. Note that in the response case, any data URL will be swapped out for the attachment ID that was generated when storing the attachment. The keys to the `notif_sounds` JSON object will be identical to the keys in the request. Just like icon and avatar uploads, a failure will cause a JSON response with the `error` string attribute.

### Message Attachment Upload

This endpoint lives at `/upload/attachments` and expects an application/json POST body containing an `attachments` attribute. This attribut should point at a list of JSON objects each containing the `filename` and `data` attributes. Additionally and optionally, an `alt_text` string attribute can also be included specifying alt text to store alongside the attachment. Additionally and optionally, a `sensitive` boolean attribute can be included specifying the image is sensitive and should be blurred by default. As you would expect, the `filename` attribute should be the filename of the file being uploaded. Note that the client can send the full path or just the filename with no directory information. In either case, CritterChat strips the directory info off as it does not need it. The `data` attribute should be a string data URL representing the attachment being uploaded. Note that as of right now, only image attachments are supported for upload. The image must be of a supported type (png, jpg, gif, apng, webp, bmp) and must not exceed the network file size for attachments. Upon successful processing of the attachments, a JSON response will be returned containing an `attachments` attribute which is a list of attachment IDs. Note that the order of attachments in the upload request will match the attachment IDs in the response. This might matter if the user has picked a particular image order and described those images in an attached message. Just like the above endpoints, a failure will cause a JSON response with the `error` string attribute.

## Common Data Types

The following data types are objects which are found in multiple packets. They are intentionally kept consistent across those packets and are thus documented here.

### room

An object representing a room. In CritterChat a room is an object that zero or more occupants can be joined to. All users who are joined to a room can request various things about the room and are sent updates that occur to the room such as chat messages sent, joins, leaves, and the like. Rooms have the following attributes:

 - `id` - A string identifier unique to the room. Can be used to uniquely and permanently refer to a room.
 - `type` - A string representing the type of the room. Public chat rooms are identified with "room" and private group chats, 1:1 chats and chats with onself are identified with "chat".
 - `name` - A string representing the current display name of the room from the requesting user's perspective. For a given 1:1 chat that hasn't had a custom name applied, this will always be set to "Chat with XXX" where XXX is the display name of the other chatter. If a custom name has been set, this will be set to that custom name.
 - `customname` - A string representing the custom name for this room. If a custom name has not been set, this will be an empty string. Clients should use this when allowing users to edit a room name instead of the `name` attribute above.
 - `topic` - A string representing the topic of the room. If a topic is not set, this will be an empty string.
 - `public` - A boolean representing whether this room is public or private. Public rooms are visible in search even when a user isn't joined to a room. Private rooms require an invite.
 - `oldest_action` - A string identifier pointing at the very first action in the room, referring to that action by its unique identifier. A client can infer that it has all actions in a room by checking to see if it has received the action identified by this string identifier. This is useful for determining if there is any additional scrollback to request.
 - `newest_action` - A string identifier pointing at the very last action in the room, referring to that action by its unique identifier. A client can infer that it has all actions in a room by checking to see if it has received the action identified by this string identifier. This is useful for determining if there are any newer messages that were missed during a disconnect.
 - `last_action_timestamp` - An integer unix timestamp representing the last action of this room. Rooms which have been modified more recently will have a larger integer than rooms which were modified further back in time. This will match the timestamp of the most recent action associated with a room.
 - `icon` - A string URI pointing at an icon resource for the room. In the case that a room does not have an icon set, this will be set to the instance default room icon.
 - `deficon` - A string URI pointing at the default room icon for this room based on instance configuration. Clients can use this to display a preview when a user chooses to unset a custom icon.

### occupant

An occupant who is or was joined to a room. In CritterChat, all rooms have zero or more occupants. There is a 1:1 mapping between users on an instance and an occupant for a given room. The only reason why there is an occupant object instead of referring directly to user objects is because CritterChat supports per-room user customizations. Occupants have the following attributes:

 - `id` - A string identifier unique to the occupant. Can be used to uniquely and permanently refer to an occupant. Even if a user leaves a room and then rejoins later, the ID remains the same.
 - `userid` - A string identifier that uniquely identifies the user behind this occupant. Can be used to uniquely and permanently refer to the user itself when fetching profile information and the like.
 - `username` - A string representing the occupant's username, as they would log in and as other occupants of a room would mention them.
 - `nickname` - A string representing the occupant's currently set nickname for this room. If the user has not customized a nickname for the room, this defaults to the user's nickname as found in their profile, and if that isn't set defaults to the user's username.
 - `icon` - A string URI pointing at the user's currently set icon for this room. If the user has not customized an icon for this room, this defaults to the user's configured icon for the instance. If that is not set, the default user avatar will be returned here instead.
 - `inactive` - A boolean representing whether this occupant has left the room (true) or if they are still in the room (false). This is useful because clients need to render names for users who have left when showing their actions in chat history, but need to show only active users in a room's user list.

### attachment

An attachment, such as an image or a downloadable file. Actions can have zero or more attachments associated with them. Attachments have the following attributes:

 - `uri` - A string URI where a browser or HTTP client can download the attachment from.
 - `mimetype` - The mime type or content type of the attachment itself. Useful for clients that wish to display different types of attachments differently.
 - `metadata` - A JSON object containing metadata about the attachment. For images, this includes the `width` and `height` attributes which represent the image's width and height after accounting for image orientation. For all attachments, an optional `alt_text` attribute can be present which is a string representing alt text for the attachment. For all attachments, an optional `sensitive` attribute can be present which is a boolean representing if the attachment is sensitive and the preview should be blurred by default.

### action

An object representing an action in a particular room. In CritterChat, actions are performed on behalf of a room occupant and stored in the room. Actions have the following attributes:

 - `id` - A string identifier unique to this action. Can be used to uniquely and permanently refer to an action.
 - `timestamp` - An integer unix timestamp representing when the action occurred.
 - `order` - An opaque integer specifying the action ordering relative to other actions. Effectively this is a monotonically increasing number, so newer actions will have a larger number than older actions. Aside from ordering, clients should refrain from using this attribute.
 - `occupant` - An occupant object detailing the occupant which performed the action.
 - `action` - A string representing the action type which occurred. Valid values are currently "message" for messages, "join" for occupants joining the chat, "leave" for occupants leaving the chat, "change_info" when an occupant changes room information such as the topic or name, and "change_profile" when an occupant changes their own personal information.
 - `details` - A JSON object that contains different details about the action depending on the action string. For "message" actions, this is an object with the `message` attribute that contains the string message that was sent, and optionally the `sensitive` boolean attribute specifying the message is sensitive and should be spoilered by default. For "join" and "leave" actions, this is an empty object since the `occupant` object contains all relevant details. For "change_info" and "change_profile" messages, this is a JSON object containing details of the change. Currently the JS client does not make use of this info outside of the "message" action.
 - `attachments` - A list of attachment objects representing any attachments that are associated with this action. Note that right now, only `message` actions can have attachments. This is usually an empty list as most messages do not contain any attachments.

### room count

An object representing the number of unread notifications for a given room. Room count objects have the following attributes:

 - `roomid` - A string identifier pointing at a particular room. Will match one of the room objects found in a variety of packets.
 - `count` - An integer count of the number of unread notifications for the given room. This will always be 0 or a positive integer.

## Client-Initiated Packets

The following packets are client-initiated. For each packet, the client request as well as the server response packet are documented together. For all packets that return a response packet with the same name as the request packet, the client can optionally add a `tag` attribute which should be a UUID. The server will ensure that the response packet has a `tag` attribute in the data containing the same UUID that was sent in the request. In this way, a client can match up responses to specific requests if need be.

### profile

The `profile` packet is sent from the client to load or refresh a user's profile. This can take an empty request JSON and looks up the profile of the logged in user. Additionally, it can take a JSON request that includes the `userid` attribute. The `userid` can be either a user ID or an occupant ID. In either case that object will be looked up and returned. Note that CritterChat supports custom icon and nickname per-room so if you want to pull up a user's custom profile for a given room you should provide an Occupant ID. If you only care about the user's generic profile you can instead specify a User ID. The server will respond with a `profile` packet with the user's profile in the response JSON with the following attributes:

 - `id` - A string identifier unique to the user that was returned. Can be used to uniquely and permanently refer to a user.
 - `username` - A string representing the user's username, as they would log in and as other users would mention them.
 - `nickname` - A string representing the user's currently set nickname. If the user has not set this, it will be defaulted to the same value as the `username`.
 - `about` - A string representing the user's about section. If the user has not set this, it will be defaulted to the empty string.
 - `icon` - A string URI pointing at the user's currently set icon. If the user has not set this, this will point at the instance default avatar.

Currently, the JS client will request the profile for the logged-in user immediately after successfully connecting to the server.

### preferences

The `preferences` packet is sent from the client to load or refresh the current user's preferences. This expects an empty request JSON and looks up the preferences of the logged in user. The server will respond with a `preferences` packet with the user's preferences in the response JSON with the following attributes:

 - `rooms_on_top` - A boolean representing whether the user wants rooms to always be displayed above conversations (true) or whether rooms and conversations should be sorted by last update (false).
 - `combined_messages` - A boolean representing whether messages sent right after each other by the same user should be combined into one chat block (true) or left as individual messages (false).
 - `color_scheme` - A string representing the user's chosen color scheme. Valid values are "light" to force light mode, "dark" to force dark mode, and "system" to let the browser pick based on system settings.
 - `title_notifs` - A boolean representing whether the user wants notifications to show up in the tab title (true) or not (false).
 - `mobile_audio_notifs` - A boolean representing whether the user wants audio notifications on mobile (true) or whether mobile clients should be silent (false).
 - `audio_notifs` - A list of strings representing which audio notifications are enabled.
 - `notif_sounds` - A JSON object keyed by audio notification type strings whose values are string URIs pointing at an audio file to play for that given notification. Note that the keys will match the list of strings in the `audio_notifs` list and a user may have notification sounds configured for notifications that they have disabled.

### lastsettings

The `lastsettings` packet is sent from the client to load or refresh the current user's last settings for this instance of the client. It expects an empty request JSON and looks up the last settings of the logged in user. Note that settings are stored per-session, meaning if a user logs in on multiple devices, each device gets separate settings. When a user logs out on a device, the settings for that device are lost. When a user logs in on a new device, the last updated settings from any other device for the same user are used to seed the settings for the current session. The server will respond with a `lastsettings` packet with the user's per-session settings in the response JSON with the following attributes:

 - `roomid` - A string representing the room that the user was last in, be it a public or private room or a 1:1 conversation.
 - `info` - A string representing whether the right side info panel is currently visible. Valid values are "shown" for currently visible, and "hidden" for currently hidden.

### motd

The `motd` packet is sent from the client to load or refresh the server message of the day. This expects an empty request JSON and looks up any server message of the day or welcome message depending on the onboarding state of the user. In the future the server may choose to respond with a `motd` packet that should contain a server message of the day which the client can choose to display to the user or make available in a modal. The server will sometimes respond with a `welcome` packet in the case that the user has not finished onboarding onto the instance.

The `welcome` packet contains the following attributes in the response JSON:

 - `message` - A string welcome message that should be displayed to the client.
 - `rooms` - A list of room objects that the user will be auto-joined to.

### roomlist

The `roomlist` packet is sent from the client to load or refresh the list of rooms that the user has currently joined. This expects an empty request JSON and looks up all joined rooms for the current user. The server will respond with a `roomlist` packet with the following attributes:

 - `rooms` - A list of room objects that the user is joined to. Note that this is sorted by most recent action to least recent action regardless of client preferences. It is up to the client to respect the `rooms_on_top` preference by sorting public rooms on top of private chats.
 - `counts` - A list of room count objects representing the number of unread actions for a given room. Note that counts are always returned when a `roomlist` packet is sent from the server in response to a `roomlist` request from the client, but not returned when a `roomlist` packet is sent after a user joins or is joined to a room.
 - `selected` - A string identifier pointing at a room in the `rooms` list that the client should select on behalf of a user. Note that the `selected` attribute is not returned when the client explicitly requests a `roomlist` response from the server, but is returned when the server sends a `roomlist` packet to the client after the user has joined or been joined to a room. When present, the client should attempt to select the room idenfied by the string identifier. When not present, the client should leave the currently selected room alone.

### chathistory

The `chathistory` packet is sent from the client to load history actions for a given room that the user has joined. This expects a request JSON with at least the `roomid` attribute, and optionally a `before` attribute. In both cases it will verify that the user is currently in the room and then return a list of actions for that room. The `roomid` attribute should be a string room identifier found in a room object as returned by a `roomlist` response from the server. When requesting without a `before` attribute this will grab the last 100 actions that occurred in the room. Note that the server expects the client to make a `chathistory` request to populate initial messages and occupants when selecting a room, either when the user clicks on a room to view messages or when the client selects a room for the user on behalf of a `selected` attribute in a `roomlist` response packet. If a `before` attribute is specified, it should be a string action identifier. The server will fetch the most recent 100 actions that come before the specified action ID placed in the `before` attribute. The client can use this behavior to implement history loading when a user scrolls up to the top of the currently populated room's actions. In both cases the server will respond with a `chathistory` response containing the following attributes:

 - `roomid` - The ID of the room that this response is for. Should always match the room ID in the request `roomid`. Clients can use this to discard stale `chathistory` response packets if the user has clicked away to another room before the response could be returned.
 - `history` - A list of action objects representing the chat history for the room. Clients wishing to request older messages can sort the received actions by the `order` attribute and then make another `chathistory` request with the action ID of the oldest action. Clients wishing to display whether there are more messages to fetch can look at the current room object's `oldest_action` identifier and compare it to the oldest action it has.
 - `occupants` - A list of occupants in the room. Note that this is only returned when the `before` attribute is not specified since in that case the client is attempting to perform an intial populate. It is assumed that when the client specifies a `before` attribute that it is fetching older actions and already has the occupant list.
 - `lastseen` - The last seen action ID for this room for the given user. Note that this is only returned when the `before` attribute is not specified. The client can use this to denote actions with a higher order than the last seen action ID as new, for the purpose of displaying what new activity has occurred since the last time the user has looked at the given room.

### chatactions

The `chatactions` packet is sent from the client to poll for newer actions to a given room that the user has joined. This expects a request JSON with the `roomid` and `after` attributes. It will verify that the user is currently in the room and then return a list of actions for that room which are newer than the specified action. The `roomid` attribute should be a string room identifier found in a room object as returned by a `roomlist` response from the server. The `after` attribute should be a string action identifier. Note that clients do not normally need to poll for updates as the server will send updates to the client automatically for all joined rooms. This is provided so that a client which has been disconnected can grab missing actions upon successfully reconnecting. The server cannot compute a reconnected client's missing messages so the client is responsible for sending a `chatactions` request with the newest action ID it knows about when reconnecting to the server. The client can determine the newest action ID by sorting known actions for a room by the `order` attribute. The server will respond with a `chatactions` response containing the following attributes:

 - `roomid` - The ID of the room that this response is for. Should always match the room ID in the request `roomid`. Clients can use this to discard stale `chatactions` response packets if the user has clicked away to another room before the response could be returned.
 - `actions` - A list of action objects representing chat history for the room. Clients wishing to denote unread actions as new should consider all of these actions as new.

### welcomeaccept

The `welcomeaccept` packet is sent from the client to inform the server that the welcome message was displayed to the user and the user accepted the message. The welcome message should be displayed when receiving a `welcome` packet in response to a `motd` request as documented above. If the user never accepts the welcome message, the client should not send the `welcomeaccept` packet to the server. When receiving the `welcomeaccept` packet the server will mark the user account as having been onboarded and respond with a `roomlist` packet as documented above. Since the user is joined to the list of rooms displayed to them upon receipt of the `welcomeaccept` packet, clients should expect the `roomlist` response to contain a `selected` attribute detailing which room to select for the user, but should not expect to receive a `counts` list since CritterChat does not attempt to badge for actions taken before the user was onboarded onto the instance.

### searchrooms

The `searchrooms` packet is sent from the client to request a list of search results given a search criteria. This expects a request JSON that contains the `name` attribute which should be a string name to search. This will cause the server to search for all rooms with a default or custom name containing the search string, and all users with user or nickname containing the search string. Search results will be limited to what rooms and users the current user is allowed to see. Searching for an empty name will return all rooms and users that the current user can see. Note that if a search for a given user is performed and the current user already has a 1:1 chat with that user, the chat will be returned instead of the user. Users will only be returned in the search result list when the current user does not have a 1:1 chat with the user. The server will respond with a `searchrooms` response containing a "rooms" attribute. This attribute is a list of room search result objects. The room search result object has the following attributes:

 - `name` - The string name of the user or room that was found matching the search criteria.
 - `handle` - The string handle of the user or room. Currently this is the username for users, and nothing for rooms, but in the future when rooms get custom URIs this will be the URI.
 - `type` - The string type of search result. Valid types are "room" for public rooms, and "chat" for private 1:1 chats or users you could chat with but have not yet.
 - `icon` - A string URI pointing to the user or room icon. In all cases this will be a valid icon, and will point at the custom icon if set or the default otherwise.
 - `public` - A boolean representing whether this search result is public or not.
 - `joined` - A boolean representing whether the user has joined the room this search result represents. Useful for clients that wish to prompt an action such as "jump to room" for joined rooms, "join room" for rooms the user has not joined, and "message user" for users.
 - `roomid` - A string identifier for the room this search result points to if the result is a room, or set to null if this search result is a user.
 - `userid` - A string identifier for the user this search result points to if the result is a user, or set to null if this search result is a room.

### updateprofile

The `updateprofile` packet is sent from the client to request the user's profile be updated. This expects a request JSON that contains the following attributes:

 - `name` - A new nickname to set. This can be empty to unset a custom nickname and it can contain emoji. It must be 255 unicode code points or less in length. It cannot consist of solely unicode control characters or other non-printable characters. Note that the user's nickname will always be set, so clients should round-trip the existing custom name if the user does not edit it.
 - `about` - A new about section to set. This can be empty to delete existin text, or non-empty to set a new text. It must be 65530 unicode code points or less in length. Note that the user's about section will always be set, so clients should round-trip the existing about section if the user does not edit it.
 - `icon` - A string attachment ID that should be used to set the new icon, obtained from the avatar upload endpoint. If this is left empty, the user's icon will not be updated. The image must be square and currently cannot exceed 128kb in size.
 - `icon_delete` - An optional boolean specifying that the user wants to delete their custom icon. If the client leaves this out or sets this to an empty string or `False` then the server will not attempt to delete the user's custom icon. Setting this to `True` will cause the user's icon to revert to the instance's default icon.

Upon successful update, the server will send a `profile` response packet which is identical to the response to a `profile` request. It will also send an unsolicited `profile` response packet to all other connected devices belonging to the user.

### updatepreferences

The `updatepreferences` packet is sent from the client to request the user's preferences be updated. This expects a request JSON that contains the following attributes:

 - `rooms_on_top` - A boolean representing whether the user wants rooms to always be displayed above conversations (true) or whether rooms and conversations should be sorted by last update (false). If not present, the preference will not be updated. If present, the preference will be updated to the specified value.
 - `combined_messages` - A boolean representing whether messages sent right after each other by the same user should be combined into one chat block (true) or left as individual messages (false). If not present, the preference will not be updated. If present, the preference will be updated to the specified value.
 - `color_scheme` - A string representing the user's chosen color scheme. Valid values are "light" to force light mode, "dark" to force dark mode, and "system" to let the browser pick based on system settings. If not present, the preference will not be updated. If present, the preference will be updated to the specified value.
 - `title_notifs` - A boolean representing whether the user wants notifications to show up in the tab title (true) or not (false). If not present, the preference will not be updated. If present, the preference will be updated to the specified value.
 - `mobile_audio_notifs` - A boolean representing whether the user wants audio notifications on mobile (true) or whether mobile clients should be silent (false). If not present, the preference will not be updated. If present, the preference will be updated to the specified value.
 - `audio_notifs` - A list of strings representing which audio notifications are enabled. If not present, individual audio notification enabled settings will be left as-is. If present, the user's audio notification enabled list is updated to match the specified list of notifications.
 - `notif_sounds` - A JSON object keyed by audio notification type strings whose values are string attachment IDs. Note that this JSON object can be obtained from the notification upload endpoint. All audio notifications listed in this JSON object will be updated, overwriting any existing notification and adding new audio for notifications that did not have audio before. If not present, no audio notification sounds will be updated. Audio notifications not present in this JSON object will also be left as-is.
 - `notif_sounds_delete` - A list of strings representing which audio notification files to delete. If not present, nothing will be deleted. If present, all notifications listed will be deleted. Note that the entries in this list are the same as the keys in `notif_sounds` and the values in the `audio_notifs` list.

Upon successful update, the server will send a `preferences` response packet which is identical to the response to a `preferences` request. It will also send an unsolicited `preferences` response packet to all other connected devices belonging to the user.

### updatesettings

The `updatesettings` packet is sent from the client any time the client toggles the "Info" panel or switches rooms, in order to inform the server of the last settings chosen by the client. Remember that settings are saved on a per-session basis so there is no need for the server to propagate settings outward to other clients nor echo the settings back to the client after successfully saving them. Therefore the client should not expect a response from this request packet. This expects a request JSON that contains the following attributes:

 - `roomid` - A string representing the room that the user was last in, be it a public or private room or a 1:1 conversation.
 - `info` - A string representing whether the right side info panel is currently visible. Valid values are "shown" for currently visible, and "hidden" for currently hidden.

### joinroom

The `joinroom` packet is sent when the client requests to join a given room. This expects a request JSON that contains the `roomid` attribute which should be a string room ID to join. This room ID can be obtained from the `roomid` attribute in a room search result object. Upon receipt of a `joinroom` request containing a valid room ID that the user is allowed to join, the user will be joined to that room. Note that the `roomid` attribute can also include a user ID to start chatting with as well. The user ID can be obtained from the `userid` attribute in a room search result object. In the case that the `roomid` attribute is actually a user ID, the server will create a new 1:1 conversation between the current user and the specified user ID and then join both people to the room. Note that if there is an existing 1:1 conversation between the requested user and the current user it will be re-used, even if the users have previously left the conversation. In that case, both users will be re-added. Upon successfully joining a room, a "join" action will be generated for the room.

In the case that the user successfully joined the requested room (or a new 1:1 chat was created) the server will respond with a `roomlist` response packet as documented above. Since the user was joined to a new room, clients should expect the `roomlist` response to contain a `selected` attribute which is the room the user just joined. The client should not expect to receive a `counts` list since CritterChat does not attempt to badge for actions taken in a room before the user joined it. Note that if the room does not exist no response will be returned. Note that if a user ID is specified and the room exists already, a `roomlist` response will be returned which includes the `selected` attribute correctly pointing to the existing 1:1 chat. Clients can use this to implement "message this user" functionality that will jump to the correct existing chat or create a new chat if one does not exist.

### updateroom

The `updateroom` packet is sent when the client requests to update the details of a particular room. This expects a request JSON that contains a `roomid` attribute representing the room being updated, as well as a `details` attribute which is a JSON object containing the attributes defined below. The server will check the user's permissions as well as verify that the user is in the room requested before performing the update. Upon successful update with at least one room detail updated, a "change_info" action will be generated for the room. The server will not respond with any specific response to this packet, but all existing clients in the room will end up receiving an unsolicited `chatactions` packet containing the "change_info" action that was generated based on this request.

 - `name` - A new custom room name to set. This can be empty to unset a custom room name and it can contain emoji. It must be 255 unicode code points or less in length. It cannot consist of solely unicode control characters or other non-printable characters. Note that the room name will always be set so clients should round-trip the existing custom room name if the user does not edit it.
 - `topic` - A new custom topic to set. Much like the above `name`, this can be empty to unset the topic, and it can contain emoji. It must also be 255 unicode code points or less and it cannot be only non-printable unicode characters. The topic will always be updated so clients should round-trip the existing topic if the user does not edit it.
 - `icon` - A string attachment ID that should be used to set the new custom room icon, obtained from the icon upload endpoint. If this is left empty, the room's icon will not be updated. The image must be square and currently cannot exceed 128kb in size.
 - `icon_delete` - An optional boolean specifying that the user wants to delete the custom room icon. If the client leaves this out or sets this to an empty string or `False` then the server will not attempt to delete the custom room icon. Setting this to `True` will cause the room's icon to revert to the instance's default icon.

### message

The `message` packet is sent when the client wishes to send a message to a room. This expects a request JSON that contains a `roomid` attribute representing the room being updated and a `message` attribute representing a string message that should be sent to the room. The server will check the user's permissions as well as verify that the user is in the room requested before adding the message to the room's action history. Note that while the message can contain any valid unicode characters, it cannot be blank and it cannot consist solely of un-printable unicode characters. Upon successful insertion of the message into the room's action history, a "message" action will be generated for the room. The server will not respond with any specific response to this packet, but all existing clients that are in the room will end up receiving an unsolicited `chatactions` packet containing the "message" action that was generated based on this request.

Optionally, the `message` packet can also include an `attachments` attribute representing any attachments that should be associated with the message. This `attachments` attribute should be a list of attachment IDs. That list can be obtained directly from the attachment upload endpoint. Note that if you do not wish to associate attachments with a given image this can be left out entirely, or it can be sent as an empty list. Both will act the same way on the server. Note that while the attachments themselves are checked in the upload, attempting to provide an attachment ID for something other than a message attachment will result in the request being rejected.

Note that while the server does not respond with a specific response, it does send a socket.io acknowledgement back in the case of either failure or success. A client can use this acknowledgement to clear user input only when successfully acknowledged by the server. The acknowledgement is a JSON object that contains a `status` attribute which is set to `success` on successful receipt and storage of the message, or `failed` under all other circumstances. Clients should not attempt to clear the user's input until a successful acknowledgement has been received in order to ensure that the user doesn't have to retype a message on error.

### leaveroom

The `leaveroom` packet is sent when the client exits a room and wishes to inform the server that it does not want updates to the room anymore, nor should it receive the room when requesting rooms in the `roomlist` packet. It expects a request JSON that contains a `roomid` attribute representing the room the user has left. Upon successfully leaving the room, a "leave" action will be generated for the room. The server will not respond with any specific response to this packet, but all remaining clients still in the room will end up receiving an unsolicited `chatactions` packet containing the "leave" action that was generated based on this request. Note that attempting to leave a room that the user is not in will result in a no-op. Note also that attempting to leave a non-existant room will result in a no-op.

### lastaction

The `lastaction` packet is sent from the client when the client catches up to a particular action in a particular room. It is used when the client wants to acknowledge receipt of actions that it previously marked as new and displayed an unread notification badge for. It expects a request JSON that contains a `roomid` attribute representing the room that the user has caught up to as well as an `actionid` representing the action that the client wishes to acknowledge read receipt of. This packet is how the client can influence the `lastseen` action ID attribute in a `chathistory` response packet. The server will not respond with any specific response to this packet, but other devices in use by the same user which are currently connected may receive an unsolicited `roomlist` response packet with an updated `counts` attribute for the room that was just updated. This is the way in which the server can communicate notifications clearing to all connected devices for the same user.

## Server-Initated Packets

The following packets are server initiated. The server will send them to correctly connected clients so that a client does not have to poll for updates.

### emotechanges

The `emotechanges` response packet will be sent to the client unsolicited whenever an administrator adds or removes custom emotes on the instance. This is sent to every connected client at the point of change so that clients do not need to refresh in order to use newly-added cusom emotes. The response JSON contains the following attributes:

 - `additions` - A JSON object keyed by string emote name, such as `:wiggle:`, with the value of each entry being the custom emote's URI as a string. Note that there is currently no way for a non-web client to retrieve the full list of custom emotes as they are embedded in the HTML template for the existing JS client. At some point when it becomes necessary this will change, but for now it is what it is.
 - `deletions` - A list of strings represnting emote names that were deleted, such as `:wiggle:`. Clients should remove any emotes listed here from any typeahead or emote search functionality and should stop attempting to replace emote text with the known URI for the emotes that were deleted.

### error

The `error` response packet will be sent to the client under any circumstance where the client attempts to make an update which violates some parameters. Examples might be trying to change a nickname to something too long or trying to set a custom icon that is too large. The response packet JSON will contain an `error` attribute which is a string error. This can be directly displayed to the user in an error popup or similar modal. Currently there is no automated way for clients to determine the error returned and translate it for the user.

### reload

The `reload` response packet will be sent to the client unsolicited whenever the server determines that the client is no longer authorized to be connected to the server. This can happen if the user's session is stale and times out, or if the user has been deactivated by an administrator. In the future this will also be used in conjunction with a "log out all other devices" feature to allow a user to safely de-authenticate any connected clients if they suspect they have been compromised. The client should respond to this by taking the user back to the login screen and asking them to re-authenticate. Upon receiving a `reload` packet, no additional requests will be handled. Instead, the server will continue sending `reload` packets to the client instead of the expected response.

### chatactions

The `chatactions` response packet will be sent to the client unsolicited whenever an action occurs in a room that the user has joined. The server has no concept of what room is active on the client so it sends all room updates to the client for every joined room. The client can use this to display new actions in the currently displayed room. For actions that are associated with a room that the client is not actively displaying, the client can instead use the actions to badge notification counts. Note that the server will only start tracking and sending new actions at the point when the client successfully connects using Socket.IO. The packet is documented in the above `chatactions` request and response for client-initiated packets since the response packet follows the same format.

### roomlist

The `roomlist` response packet will be sent to the client unsolicited when the user's joined room information is updated not in response to the client's request. Right now that includes when the user is joined to a room by another user (such as starting a new 1:1 chat and in the future being added to a chat by an administrator or by invite) and when notification badges are cleared for a given room. The latter happens when the user is using multiple devices and views new actions in a room on another device. CritterChat informs all other connected clients for that user so that the user doesn't have to manually click on each room to clear notifications for every device they are actively signed on with. It is documented in the above `roomlist` request and response for client-initiated packets since the response packet follows the same format.

### profile

The `profile` response packet will be sent to the client unsolicited when the user's profile is updated not in response to the client's request. This can happen if an administrator changes a user's profile information or when the user edits their own profile on another device. When this happens the server will send a `profile` response to all devices so that they can get an updated version of the user's profile. The packet is documented in the above `profile` request and response for client-initated packets since the response packet follows the same format.

### preferences

The `preferences` response packet will be sent to the client unsolicited when the user's preferences are updated not in response to the client's request. This happens when the user edits their preferences on another device. When this happens the server will send a `preferences` response to all devices so that they can get an updated version of the user's preferences. The packet is documented in the above `preferences` request and response for client-initated packets since the response packet follows the same format.
