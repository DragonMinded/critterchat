import $ from "jquery";
import { flash } from "../utils.js";

/**
 * Handles taking base64-encoded URL data and uploading it to the backend, getting in
 * return an attachment ID that can be used to refer to an attachment of some type.
 * Used for uploading room icons, avatars, message attachments and notification sounds.
 */
class Uploader {
    constructor() {
        // This constructor intentionally left blank.
    }

    _uploadSingle(url, data, callback) {
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

    uploadIcon(data, callback) {
        this._uploadSingle(window.uploadIcon, data, callback);
    }

    uploadAvatar(data, callback) {
        this._uploadSingle(window.uploadAvatar, data, callback);
    }
}

export { Uploader };
