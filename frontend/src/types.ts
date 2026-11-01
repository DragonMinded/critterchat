// We don't allow the client to know anything about IDs, they should be seen as opaque.
export type ID = string;

// The below are all interface definitions for types that we expect from the server.
export interface Settings {
    info?: string;
    roomid?: ID;
}

export interface Preferences {
    rooms_on_top: boolean;
    combined_messages: boolean;
    color_scheme: "light" | "dark" | "system";
    desktop_size: "smallest" | "smaller" | "normal" | "larger" | "largest";
    mobile_size: "smallest" | "smaller" | "normal" | "larger" | "largest";
    admin_controls: "visible" | "hidden";
    title_notifs: boolean;
    search_privacy: "visible" | "hidden";
    invite_privacy: "auto_accept" | "choose" | "disallow";
    mobile_audio_notifs: boolean;
    tabbable_chat_elements: boolean;
    audio_notifs: string[];
    notif_sounds: {[index: string]:string};
    low_motion: boolean;
}

export interface Room {
    id: ID;
    type: string;
    name: string;
    customname: string;
    topic: string;
    public: boolean;
    moderated: boolean;
    autojoin: boolean;
    oldest_action: ID | null;
    newest_action: ID | null;
    last_action_timestamp: number;
    icon: string | null;
    lmicon: string | null;
    deficon: string;
}

export interface User {
    id: ID;
    username: string;
    nickname: string;
    about: string;
    icon: string | null;
    lmicon: string | null;
}

export interface Invite {
    id: ID;
    user: User | null;
    timestamp: number;
    room?: Room;
    cancellable?: boolean;
    active?: boolean;
    seen?: boolean;
}

export interface Occupant {
    id: ID;
    userid: ID;
    username: string;
    nickname: string;
    present: boolean;
    inactive: boolean;
    moderator: boolean;
    muted: boolean;
    invite: Invite | null;
    icon: string | null;
    lmicon: string | null;
}

export interface Attachment {
    uri: string;
    mimetype: string;
    metadata: object;
}

export interface Details {
    // Sometimes present on JOIN and LEAVE actions to specify if they were added or removed by somebody.
    actor?: ID;

    // Present on CHANGE_MESSAGE actions to specify who changed the message (could be somebody reacting).
    actionid?: ID;

    // Present on INVITE_USER actions to specify who invited the occupant.
    invited?: ID;

    // Present on UNINVITE_USER actions to specify who uninvited the occupant.
    uninvited?: ID;

    // These are present on MESSAGE actions.
    message?: string;
    reactions?: {[index: string]:string[]};

    // Present on MESSAGE actions when the message was resent due to being modified.
    modified?: boolean;

    // These are present on CHANGE_MESSAGE actions to specify what was changed.
    edited?: string[];
    add?: string;
    remove?: string;
}

export interface Action {
    id: ID;
    order: number;
    timestamp: number;
    occupant: Occupant | null;
    action: string;
    details: Details;
    attachments: Attachment[];
}
