import { io, Socket as ClientSocket } from "socket.io-client";
import { v4 as uuidv4 } from "uuid";

// Standard event callback for when an on() handler fires.
type EvtCallback = (request: any) => void;

// Tagged request callback, for the packet response associated with the tag and a previous request.
type ReqCallback = (evt: string, response: any) => void;

// socket.io packet acknowledgement callback.
type AckCallback = (acknowledgement: any) => void;

// Data object, which should have a tag.
interface TaggedObject {
    tag?: string;
}

/**
 * Handles providing an event and tag based callback system on top of socket.io
 * websockets. This was designed to share a similar interface to socket.io's own
 * JS client for developer familiarity as well as drop-in support.
 */
class Socket {
    callbacks: Map<string, EvtCallback[]>;
    tags: Map<string, ReqCallback>;
    socket: ClientSocket;
    connected: boolean;

    constructor( loc: string ) {
        // Set up callbacks for packet handling.
        this.callbacks = new Map();
        this.tags = new Map();

        // Connect to server.
        this.socket = io(loc);
        this.connected = true;
        this.socket.on('connect', () => { this._call("connect", {}); });
        this.socket.on('disconnect', () => { this._call("disconnect", {}); });
        this.socket.onAny((evt: string, ...args) => {
            this._handle(evt, args[0]);
        });
    }

    _call( evt: string, data: object ): void {
        if (this.callbacks.has(evt)) {
            const handlers = this.callbacks.get(evt)!;
            handlers.forEach((handler) => {
                handler(data);
            });
        }
    }

    _handle( evt: string, data: TaggedObject ): void {
        if (data.tag) {
            // This is a response to a request.
            const tag = data.tag;
            delete data.tag;

            if (this.tags.has(tag)) {
                // We recognize the handler. Call it and then nuke the handler from our registry.
                const handler = this.tags.get(tag)!;
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

    connect(): void {
        this.socket.connect();
        this.connected = true;
    }

    disconnect(): void {
        this.connected = false;
        this.socket.disconnect();
    }

    on( evt: string, callback: EvtCallback ): void {
        if (!this.callbacks.has(evt)) {
            this.callbacks.set(evt, [callback]);
        } else {
            this.callbacks.get(evt)!.push(callback);
        }
    }

    emit( evt: string, data: object, ack?: AckCallback ): void {
        if (!this.connected) {
            return;
        }

        if (ack) {
            this.socket.emit(evt, data, ack);
        } else {
            this.socket.emit(evt, data);
        }
    }

    request( evt: string, data: object, callback: ReqCallback, ack?: AckCallback ): void {
        if (!this.connected) {
            return;
        }

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
