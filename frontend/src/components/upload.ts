import $ from "jquery";
import { flash } from "../utils";

type ID = string;
type SingleCallback = (aid: ID) => void;
type MultiCallback = (aids: ID[]) => void;

// These are provided by the backend when it renders out the HTML we're part of.
declare global {
    interface Window {
        uploadIcon: string;
        uploadAvatar: string;
        uploadAttachments: string;
        uploadNotifications: string;
    }
}

/**
 * Handles taking base64-encoded URL data and uploading it to the backend, getting in
 * return an attachment ID that can be used to refer to an attachment of some type.
 * Used for uploading room icons, avatars, message attachments and notification sounds.
 */
class Uploader {
    constructor() {
        // This constructor intentionally left blank.
    }

    _uploadSingle(url: string, data: object, callback: SingleCallback): void {
        $.ajax(
            url,
            {
                method: "POST",
                contentType: "text/plain",
                data: data,
                processData: false,
                error: (xhr) => {
                    const resp = JSON.parse(xhr.responseText);
                    flash('warning', resp.error);
                },
                success: (data) => {
                    callback(data.attachmentid);
                }
            }
        );
    }

    uploadIcon(data: object, callback: SingleCallback) {
        this._uploadSingle(window.uploadIcon, data, callback);
    }

    uploadAvatar(data: object, callback: SingleCallback) {
        this._uploadSingle(window.uploadAvatar, data, callback);
    }

    uploadNotificationSounds(data: object, callback: MultiCallback) {
        $.ajax(
            window.uploadNotifications,
            {
                method: "POST",
                contentType: "application/json",
                data: JSON.stringify({notif_sounds: data}),
                processData: false,
                error: (xhr) => {
                    const resp = JSON.parse(xhr.responseText);
                    flash('warning', resp.error);
                },
                success: (newData) => {
                    callback(newData.notif_sounds);
                }
            }
        );
    }

    uploadAttachments(data: object, callback: MultiCallback) {
        $.ajax(
            window.uploadAttachments,
            {
                method: "POST",
                contentType: "application/json",
                data: JSON.stringify({attachments: data}),
                processData: false,
                error: (xhr) => {
                    const resp = JSON.parse(xhr.responseText);
                    flash('warning', resp.error);
                },
                success: (newData) => {
                    callback(newData.attachments);
                }
            }
        );
    }
}

export { Uploader };
