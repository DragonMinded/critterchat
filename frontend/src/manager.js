import $ from "jquery";

import { InputState } from "./inputstate.js";
import { ScreenState } from "./screenstate.js";
import { EventHandler } from "./components/event.js";
import { Uploader } from "./components/upload.js";
import { AudioNotifications } from "./components/audionotifs.js";

import { Menu } from "./menu.js";
import { Messages } from "./messages.js";
import { Info } from "./info.js";
import { Profile } from "./modals/profile.js";

import { escapeHtml, flash, flashHook, containsStandaloneText } from "./utils.js";
import { displayInfo } from "./modals/infomodal.js";

/**
 * The socket and event manager for CritterChat's frontend. The various major components of the
 * frontend are created here and managed from within this class. Only the manager handles socket
 * communications. Everything else handles communication via events which are broadcast for one
 * of two purposes. The first purpose is for the manager to handle some request, such as loading
 * chat history when we navigate to a new chat. The second purpose is to inform systems that
 * something has happened, such as the user toggling info or a notification occurring. This helps
 * keep various components decoupled and handling only their section of the UI while allowing
 * the components to interact with each other when necessary.
 *
 * For the above to work, we create an event bus that gets passed to all components of the UI
 * as they are created. Anyone can emit events to this event bus, and anyone can listen for
 * events that they care about on this event bus. For the majority of events, there is only
 * really one emitter and one listener. But that still allows us to keep the various components
 * decoupled and only broadcast intents and requests.
 *
 * We also handle global input and screen state in the manager. The input state is the state
 * of any typeahead/autocomplete popover or emoji search popover that the user might be interacting
 * with at any given time. Because only one is allowed open at once, we handle informing the two
 * systems that one should close should the other be opened by allowing both to register input
 * state listeners. Similarly, when in mobile mode we only display one screen at a time. Therefore
 * the various screens would need to coordinate transitioning between each other. We do so using
 * the screen state which allows the various components to coordinate passing UI control between
 * each other depending on user request.
 */
export function manager(socket) {
    var eventBus = new EventHandler();
    var inputState = new InputState();
    var screenState = new ScreenState();
    var uploader = new Uploader();

    // Tracks all known rooms that we are in and the last known action in each room. Used to
    // request missing actions that were sent while we were disconnected upon reconnect.
    var rooms = new Map();

    // Tracks the user's last settings, such as what room they are in and the info panel visibility.
    var settings = {};

    // Tracks the determined window size and handles the understanding of whether we're displaying
    // in desktop mode (vertical panels available) or mobile mode (one screen at a time and using
    // the screen state to coordinate moving between screens).
    var size = $( window ).width() <= 700 ? "mobile" : "desktop";
    var desktopSize = "normal";
    var mobileSize = "normal";

    // Tracks whether we are currently the active, visible tab or a background tab.
    var visibility = document.visibilityState;

    // Handles the left hand menu panel which shows all joined rooms and private conversations.
    var menuInst = new Menu(eventBus, screenState, inputState, size, visibility);

    // Handles the center chat panel.
    var messagesInst = new Messages(eventBus, screenState, inputState, size, visibility);

    // Handles the right hand info panel which shows joined chatters, as well as handling the
    // info pane above the message instance.
    var infoInst = new Info(eventBus, screenState, inputState, size, visibility);

    // Handles audio notification playback.
    var notifInst = new AudioNotifications(eventBus, size, visibility);

    // Handles the profile view popover, not owned by any one panel since it can be summoned
    // by multiple of them.
    var profileInst = new Profile(eventBus);

    // Ensure any server-generated messages are closeable.
    flashHook();

    // Check for application updates. The only thing this manages is a little info flash that
    // tells a user they can refresh for a new version, which is dismissable if they do not
    // want to do so.
    function checkForUpdates() {
        $.getJSON(window.versionCheck, function( data ) {
            if (data.js != window.version) {
                window.version = data.js;
                flash( 'info', 'There is a new version of ' + window.appname + ' available. Refresh to upgrade!' );
            }
        });
    }

    // Arbitrarily chosen to be a 15 second interval.
    setInterval(checkForUpdates, 1000 * 15);

    // Socket callback that occurs every time we successfully connect to the backend server
    // via our websocket connection. This happens on document load for the initial connection,
    // but can also happen if the client loses its connection to the server and then establishes
    // a new connection later.
    socket.on('connect', () => {
        // Let our various subsystems know we made a connection to the server.
        eventBus.emit('connected', {});

        // Ask for our profile and last settings so we can refresh where we left off.
        socket.emit('profile', {});
        socket.emit('preferences', {});
        socket.emit('lastsettings', {});

        // Poll the server for any missed updates while we were potentially disconnected. Do
        // this before the room list so we don't get our last events overwritten. On first
        // connect the rooms map will always be empty, and on subsequent connections the rooms
        // map will contain the last action we received for every room.
        rooms.forEach((room) => {
            socket.emit('chatactions', {roomid: room.id, after: room.newest_action})
        });

        // Ask for our list of rooms that we're in.
        socket.emit('roomlist', {});

        // Ask for any server MOTD or admin messages.
        socket.emit('motd', {});
    });

    // Socket callback that occurs every time we lose connection to the backend server. This
    // ideally should never happen but it can for two reasons. First, the server itself can
    // go down, either due to an error or due to being updated. Second, the network between
    // the client and the server can go down, such as losing mobile signal or similar.
    socket.on('disconnect', () => {
        // Let our various subsystems know we lost our connection to the server.
        eventBus.emit('disconnected', {});
    });

    // On occasion when the server has determined we've deauthed our session, it will send a
    // reload request. We comply by refreshing the page, which under normal circumstances will
    // re-validate the session, realize the user is logged out or deactivated, and redirect
    // the user to the login screen to reauth.
    socket.on('reload', () => {
        // Server wants us to reload, probably to de-auth ourselves after a remote logout.
        window.location.reload();
    });

    // Handles re-calculating whether we're desktop or mobile when receiving a resize event.
    // Broadcasts that new size whenever we pass a threshold using the "resize" event so
    // various systems can listen and react accordingly.
    $( window ).on( "resize", () => {
        const width = $( window ).width();
        const newSize = width <= 700 ? "mobile" : "desktop";

        if (newSize != size) {
            $( "body" ).removeClass("smallest").removeClass("smaller").removeClass("normal").removeClass("larger").removeClass("largest");
            if (newSize == "mobile") {
                $( "body" ).addClass(mobileSize);
            } else {
                $( "body" ).addClass(desktopSize);
            }

            size = newSize;
            eventBus.emit('resize', size);
        }
    });

    // Handles re-calculating whether we're the active tab or a background tab. Broadcasts
    // that visibility using the "updatevisibility" event so various systems can listen and
    // react accordingly.
    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState != visibility) {
            visibility = document.visibilityState;
            eventBus.emit('updatevisibility', visibility);
        }
    });

    // Instead of having a separate file and class for the welcome popover, we just handle
    // it here. Possibly bad, possibly okay, but it works and isn't hurting anyone so it
    // lives here for now. There's no real reason why it needs to be here versus in its own
    // separate class aside from the extra overhead of setting that up.
    socket.on('welcome', (msg) => {
        var html = "";
        msg.rooms.forEach((result) => {
            var id = result.roomid;
            var type = result.type == "room" ? 'room' : 'avatar';

            html += '<div class="item" id="' + id + '">';
            html += '  <div class="icon ' + type + '">';
            html += '    <img src="' + result.icon + '" />';
            if (result.type == 'room') {
                html    += '    <div class="room-indicator">#</div>';
            }
            html += '  </div>';
            html += '  <div class="name-wrapper"><div class="name">' + escapeHtml(result.name) + '</div></div>';
            html += '</div>';
        });

        displayInfo(
            '<div class="welcome-message">' + msg.message + '</div><div class="results">' + html + '</div>',
            'okay!',
            () => {
                socket.emit('welcomeaccept', {});
            }
        );
    });

    // Handles displaying a little info popover whenever the server sends us a dislayable error.
    // In the future it would be nice if errors included IDs so we can have client-side translations
    // for multi-language support.
    socket.on('error', (msg) => {
        displayInfo(
            msg.error,
            'okay!',
        );
    })

    socket.on('roomlist', (msg) => {
        if (msg.rooms) {
            // First, track the rooms ourselves so we can handle notification generation.
            const newRooms = new Map();
            msg.rooms.forEach((room) => {
                newRooms.set(room.id, room);
            });
            rooms = newRooms;

            // Now, notify our various systems that we got an updated list of rooms that we're in.
            // This list is always absolute, not a delta, so the various systems will calculate
            // deltas as needed.
            menuInst.setRooms(msg.rooms);
            infoInst.setRooms(msg.rooms);
            messagesInst.setRooms(msg.rooms);
        }
        if (msg.counts) {
            // Notify our various systems that the notification badge counts have changed, likely
            // due to a different device acknowledging notifications for a room this client is
            // not actively viewing.
            menuInst.setBadges(msg.counts);
        }
        if (msg.selected) {
            // Notify our various systems that the server has requested we select a particular
            // room. This only happens when we request to join a new room or start a new chat.
            menuInst.selectRoom(msg.selected);
        }
    });

    socket.on('lastsettings', (msg) => {
        // Keep an updated copy of our settings for ourselves.
        settings = msg;

        // Notify various systems that per-session settings have been sent to us. Because the
        // settings are per-session, we never receive a lastsettings that we didn't request.
        // So, various systems should not expect to react to this message more than once per
        // successful connection.
        menuInst.setLastSettings(msg);
        messagesInst.setLastSettings(msg);
        infoInst.setLastSettings(msg);
    });

    socket.on('profile', (msg) => {
        if (msg.id == window.userid) {
            // This should never change, but if we have info about it, let's update anyway.
            window.username = msg.username;

            // Notify various systems that our profile has been updated, so they can grab
            // things such as the nickname and our avatar.
            menuInst.setProfile(msg);
            messagesInst.setProfile(msg);
            infoInst.setProfile(msg);
        }
    });

    socket.on('preferences', (msg) => {
        // Handle setting a root-level class that forces light or dark mode selection using
        // CSS selectors. In the instance the user chose system setting, just removes all
        // overrides and lets the browser choose the right color scheme automatically.
        if (msg.color_scheme == "light") {
            $( "body" ).removeClass("dark").addClass("light");
        } else if (msg.color_scheme == "dark") {
            $( "body" ).removeClass("light").addClass("dark");
        } else {
            $( "body" ).removeClass("light").removeClass("dark");
        }

        desktopSize = msg.desktop_size;
        mobileSize = msg.mobile_size;

        $( "body" ).removeClass("smallest").removeClass("smaller").removeClass("normal").removeClass("larger").removeClass("largest");
        if (size == "mobile") {
            $( "body" ).addClass(mobileSize);
        } else {
            $( "body" ).addClass(desktopSize);
        }

        // Notify various systems that preferences were updated and allow them to redraw
        // as needed based on the updated preferences.
        menuInst.setPreferences(msg);
        messagesInst.setPreferences(msg);
        infoInst.setPreferences(msg);
        notifInst.setPreferences(msg);
    });

    socket.on('chathistory', (msg) => {
        if (msg.occupants) {
            // Notify systems that are concerned with occupants that we got a complete list of occupants.
            // This happens on the first load of chat history under normal circumstances, and then does
            // not happen again since the various components can use actions such as "join" and "leave"
            // that come in through the below "chatactions" hook to keep user lists updated.
            messagesInst.setOccupants(msg.roomid, msg.occupants);
            infoInst.setOccupants(msg.roomid, msg.occupants);
        }

        // Notify systems that are concerned with history that we got a new chunk of history. This
        // happens on first load as well as when the user scrolls up to the top of the currently loaded
        // history and we request more history.
        messagesInst.updateHistory(msg.roomid, msg.history, msg.lastseen);
    });

    socket.on('chatactions', (msg) => {
        // First, regardless of the room, figure out if any notification sounds should be
        // generated from these messages. This is as good a place as any to handle what types of
        // actions generate notifications. Note that this is done here and not in the above
        // "chathistory" listener because the above packet handles bulk history fetching where
        // this handles getting notified of new actions that just occurred.
        var roomType = undefined;
        if (rooms.has(msg.roomid)) {
            roomType = rooms.get(msg.roomid).type;
        }

        if (roomType) {
            msg.actions.forEach((message) => {
                if (message.action == "join") {
                    if (message.occupant.username != window.username) {
                        eventBus.emit("notification", {"action": "join", "type": roomType});
                    }
                } else if (message.action == "leave") {
                    if (message.occupant.username != window.username) {
                        eventBus.emit("notification", {"action": "leave", "type": roomType});
                    }
                } else if (message.action == "message") {
                    if (message.occupant.username == window.username) {
                        eventBus.emit("notification", {"action": "messageSend", "type": roomType})
                    } else {
                        const escaped = escapeHtml(message.details.message);
                        const actualuser = '@' + window.username;
                        if (containsStandaloneText(escaped, actualuser)) {
                            eventBus.emit("notification", {"action": "mention", "type": roomType});
                        } else {
                            eventBus.emit("notification", {"action": "messageReceive", "type": roomType});
                        }
                    }
                }
            });
        }

        // Grab the newest action out of the action list so we can update our room action tracker. This
        // ends up being used when we disconnect and reconnect without a page refresh, so we know what
        // action we left off on and can request any actions we missed that were newer than our known actions.
        if (rooms.has(msg.roomid)) {
            var lastAction = {};
            msg.actions.forEach((message) => {
                if (!lastAction?.order) {
                    lastAction = message;
                } else {
                    if (message.order > lastAction.order) {
                        lastAction = message;
                    }
                }
            });
            rooms.get(msg.roomid).newest_action = lastAction;
        }

        // Now, notify various subsystems of new actions that just occurred.
        messagesInst.updateActions(msg.roomid, msg.actions);
        menuInst.updateActions(msg.roomid, msg.actions);
        infoInst.updateActions(msg.roomid, msg.actions);
    });

    socket.on('searchrooms', (msg) => {
        // Pretty self-explanatory, handles ferrying any search results sent from the server to the
        // search instance for update.
        menuInst.populateSearchResults(msg.rooms);
    });

    socket.on('emotechanges', (msg) => {
        // Handles notifying various systems about any newly added or newly removed custom server emotes.
        messagesInst.addEmotes(msg.additions);
        messagesInst.deleteEmotes(msg.deletions);
    });

    eventBus.on('displayprofile', (occupantid) => {
        // We were notified that the user wants to view a profile. Fire off a load request for the
        // profile and display the modal.
        profileInst.display();

        socket.request('profile', {'userid': occupantid}, (evt, data) => {
            if (evt != 'profile') {
                // TODO: How do we surface this back to the server or somewhere meaningful?
                console.log("Got unexpected event " + evt + " back from profile lookup request!");
            } else {
                // We got a profile response for a different user, display that on profile view.
                profileInst.setProfile(data);
            }
        });
    });

    eventBus.on('selectroom', (roomid) => {
        // We were notified that the user selected a new room. Update our copy of settings and then
        // inform the server so it can save that updated room in our per-session settings. This allows
        // us to re-open that same room on refresh or when closing and re-opening the client.
        settings.roomid = roomid;
        socket.emit('updatesettings', settings);

        // Inform various systems that the room has changed.
        messagesInst.setRoom(roomid);
        infoInst.setRoom(roomid);

        // Handle requesting history since that's the first thing that needs to happen when selecting
        // a new room.
        socket.emit('chathistory', {roomid: roomid});
    });

    eventBus.on('loadhistory', (info) => {
        socket.emit('chathistory', {roomid: info.roomid, before: info.before});
    });

    eventBus.on('loadactions', (info) => {
        socket.emit('chatactions', {roomid: info.roomid, after: info.after});
    });

    eventBus.on('updateinfo', (info) => {
        // We were notified that the user toggled the info panel. Update our copy of settings and then
        // inform the server so it can save the current toggle state of the info panel. This means that
        // on refreshing or closing and reopening the client we will persist whether the info panel was
        // open or closed.
        settings.info = info;
        socket.emit('updatesettings', settings);
    });

    eventBus.on('updateprofile', (profile) => {
        if (profile.icon) {
            // Need to upload the new icon and get the attachment ID back.
            uploader.uploadAvatar(profile.icon, (iconid) => {
                profile.icon = iconid;
                socket.emit('updateprofile', profile);
            });
        } else {
            // No need to upload anything, no icon changes.
            socket.emit('updateprofile', profile);
        }
    });

    eventBus.on('updatepreferences', (preferences) => {
        if ($.isEmptyObject(preferences.notif_sounds)) {
            socket.emit('updatepreferences', preferences);
        } else {
            uploader.uploadNotificationSounds(preferences.notif_sounds, (sounds) => {
                preferences.notif_sounds = sounds;
                socket.emit('updatepreferences', preferences);
            });
        }
    });

    eventBus.on('leaveroom', (roomid) => {
        // Inform the server so it can generate an action for all other occupants in the room to see
        // that we left the room, and so the server stops sending us room upates since we left.
        socket.emit('leaveroom', {'roomid': roomid})

        // Inform the various systems that they should stop tracking and displaying this room.
        messagesInst.closeRoom(roomid);
        infoInst.closeRoom(roomid);
        menuInst.closeRoom(roomid);
    });

    eventBus.on('joinroom', (roomoruserid) => {
        socket.emit('joinroom', {'roomid': roomoruserid})
    });

    eventBus.on('updateroom', (msg) => {
        const roomid = msg.roomid;
        var details = msg.details;

        if (details.icon) {
            // Need to upload the new icon and get the attachment ID back.
            uploader.uploadIcon(details.icon, (iconid) => {
                details.icon = iconid;
                socket.emit('updateroom', {'roomid': roomid, 'details': details});
            });
        } else {
            // No need to upload anything, no icon changes.
            socket.emit('updateroom', {'roomid': roomid, 'details': details});
        }
    });

    eventBus.on('message', (msg) => {
        const roomid = msg.roomid;
        const message = msg.message;
        var attachments = msg.attachments;

        if (attachments.length > 0) {
            // Need to upload attachments first before sending message.
            uploader.uploadAttachments(attachments, (aids) => {
                socket.emit('message', {'roomid': roomid, 'message': message, 'attachments': aids}, (response) => {
                    if (response.status == "success") {
                        eventBus.emit('messageack', {'roomid': msg.roomid, 'status': 'success'});
                    } else {
                        eventBus.emit('messageack', {'roomid': msg.roomid, 'status': 'failure'});
                    }
                });
            });
        } else {
            socket.emit('message', {'roomid': roomid, 'message': message}, (response) => {
                if (response.status == "success") {
                    eventBus.emit('messageack', {'roomid': msg.roomid, 'status': 'success'});
                } else {
                    eventBus.emit('messageack', {'roomid': msg.roomid, 'status': 'failure'});
                }
            });
        }
    });

    eventBus.on('searchrooms', (value) => {
        socket.emit('searchrooms', {'name': value})
    });

    eventBus.on('lastaction', (value) => {
        // Inform the server of the last action the client read for a given room.
        socket.emit('lastaction', value);
    });
}
