import { io } from "socket.io-client";
import { v4 as uuidv4 } from "uuid";

/**
 * Handles providing an event and tag based callback system on top of socket.io
 * websockets. This was designed to share a similar interface to socket.io's own
 * JS client for developer familiarity as well as drop-in support.
 */
class Socket {
    constructor( loc ) {
        this.callbacks = new Map();
        this.tags = new Map();
        this.socket = undefined;

        if ( loc ) {
            this.connect(loc);
        }
    }

    _call( evt, data ) {
        if (this.callbacks.has(evt)) {
            const handlers = this.callbacks.get(evt);
            handlers.forEach((handler) => {
                handler(data);
            });
        }
    }

    _handle( evt, data ) {
        if (data.tag) {
            // This is a response to a request.
            const tag = data.tag;
            delete data.tag;

            if (this.tags.has(tag)) {
                // We recognize the handler. Call it and then nuke the handler from our registry.
                const handler = this.tags.get(tag);
                handler(evt, data);
                this.tags.delete(tag);
            } else {
                // TODO: How to surface this or send to server?
                console.log("Response received with tag " + tag + " does not have a handler!")
            }
        } else {
            // This is just an event we should call.
            this._call(evt, data);
        }
    }

    connect( loc ) {
        this.socket = io.connect(loc);
        this.socket.on('connect', () => { this._call("connect", {}); });
        this.socket.on('disconnect', () => { this._call("disconnect", {}); });
        this.socket.onAny((evt, ...args) => {
            this._handle(evt, args[0]);
        });
    }

    on( evt, callback ) {
        if (!this.callbacks.has(evt)) {
            this.callbacks.set(evt, [callback]);
        } else {
            this.callbacks.get(evt).push(callback);
        }
    }

    emit( evt, data, ack ) {
        if (ack) {
            this.socket.emit(evt, data, ack);
        } else {
            this.socket.emit(evt, data);
        }
    }

    request( evt, data, callback, ack ) {
        const tag = uuidv4();

        this.tags.set(tag, callback);

        if (ack) {
            this.socket.emit(evt, {...data, tag: tag}, ack);
        } else {
            this.socket.emit(evt, {...data, tag: tag});
        }
    }
}

export { Socket };
