# Protocol Documentation

This is an attempt to document the websocket protocol provided by CritterChat's backend and used by CritterChat's frontend. This serves two purposes. First, it allows a high-level overview that hopefully sidesteps some new developer ramp-up time. Second, it hopefully aids in alternative clients being developed without them having to reverse-engineer everything from as-built code.

At the high level, communcation between the existing web-based JS client and the backend server is done via [https://socket.io/](socket.io) which uses websockets under the hood. Socket.IO presents an event-driven interface which we view as named JSON packets. The various packets, whether they are server or client-originated, what they do, and when you should expect to send or receive them is all documented below.

## Authentication

Authentication is not handled by websockets in CritterChat. Instead, there is a POST method accepting browser form data which sets a `SessionID` cookie. In the future, I'd like this endpoint to be versatile enough to accept both form data in the post body for browser-based login and JSON in the post body for alternative clients. For now, the important part of this interaction is the `SessionID` cookie that is sent back to the client which should be present on the websocket connection itself. All websocket requests use this cookie to link the websocket session to a logged-in user. If a session is invalidated for any reason, the server will respond to any request with a `reload` packet instructing the client to reload and redo authentication to get a new `SessionID` cookie.

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
 - `last_action` - An integer unix timestamp representing the last action of this room. Rooms which have been modified more recently will have a larger integer than rooms which were modified further back in time. This will match the timestamp of the most recent action associated with a room.
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

### action

An object representing an action in a particular room. In CritterChat, actions are performed on behalf of a room occupant and stored in the room. Actions have the following attributes:

 - `id` - A string identifier unique to this action. Can be used to uniquely and permanently refer to an action.
 - `timestamp` - An integer unix timestamp representing when the action occurred.
 - `order` - An opaque integer specifying the action ordering relative to other actions. Effectively this is a monotonically increasing number, so newer actions will have a larger number than older actions. Aside from ordering, clients should refrain from using this attribute.
 - `occupant` - An occupant object detailing the occupant which performed the action.
 - `action` - A string representing the action type which occurred. Valid values are currently "message" for messages, "join" for occupants joining the chat, "leave" for occupants leaving the chat, "change_info" when an occupant changes room information such as the topic or name, and "change_profile" when an occupant changes their own personal information.
 - `details` - A string that contains different details about the action depending on the action string. For "message" actions, this is the string message that was sent. For "join" and "leave" actions, this is an empty string since the `occupant` object contains all relevant details. For "change_info" and "change_profile" messages, this is a JSON string containing details of the change. Currently the JS client does not make use of this info and in the future this might be changed to return nested JSON directly instead of a string containing JSON.

### room count

An object representing the number of unread notifications for a given room. Room count objects have the following attributes:

 - `roomid` - A string identifier pointing at a particular room. Will match one of the room objects found in a variety of packets.
 - `count` - An integer count of the number of unread notifications for the given room. This will always be 0 or a positive integer.

## Client-Initiated Packets

The following packets are client-initiated. For each packet, the client request as well as the server response packet are documented together.

### profile

The `profile` packet is sent from the client to load or refresh a user's profile. Currently it expects an empty request JSON and looks up the profile of the logged in user. In the future this will also support requesting the profile of another user by that user's ID in the request JSON. The server will respond with a `profile` packet with the user's profile in the response JSON with the following attributes:

 - `id` - A string identifier unique to the user that was returned. Can be used to uniquely and permanently refer to a user.
 - `username` - A string representing the user's username, as they would log in and as other users would mention them.
 - `nickname` - A string representing the user's currently set nickname. If the user has not set this, it will be defaulted to the same value as the `username`.
 - `icon` - A string URI pointing at the user's currently set icon. If the user has not set this, this will point at the instance default avatar.

Currently, the JS client will request the profile for the logged-in user immediately after successfully connecting to the server.

### preferences

The `preferences` packet is sent from the client to load or refresh the current user's preferences. This expects an empty request JSON and looks up the preferences of the logged in user. The server will respond with a `preferences` packet with the user's preferences in the response JSON with the following attributes:

 - `rooms_on_top` - A boolean representing whether the user wants rooms to always be displayed above conversations (true) or whether rooms and conversations should be sorted by last update (false).
 - `color_scheme` - A string representing the user's chosen color scheme. Valid values are "light" to force light mode, "dark" to force dark mode, and "system" to let the browser pick based on system settings.
 - `title_notifs` - A boolean representing whether the user wants notifications to show up in the tab title (true) or not (false).
 - `mobile_audio_notifs` - A boolean representing whether the user wants audio notifications on mobile (true) or whether mobile clients should be silent (false).
 - `audio_notifs` - A list of strings representing which audio notifications are enabled.
 - `notif_sounds` - A dictionary keyed by audio notification type strings whose values are string URIs pointing at an audio file to play for that given notification. Note that the keys will match the list of strings in the `audio_notifs` list and a user may have notification sounds configured for notifications that they have disabled.

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

### chatactions

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

### updatepreferences

### updatesettings

### joinroom

### updateroom

### message

### leaveroom

### lastaction
