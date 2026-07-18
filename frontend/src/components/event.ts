type HandlerCallback = (data: any) => void;

/**
 * Handles providing a simple event broadcaster and listener interface. Originally
 * based on npm's event library, but that was way too much code for such a simple
 * functionality so this was written in its stead.
 */
class EventHandler {
    callbacks: Map<string, HandlerCallback[]>;
    deferreds: Map<string, HandlerCallback[]>;

    constructor() {
        this.callbacks = new Map();
        this.deferreds = new Map();
    }

    _call(evt: string, data: any): void {
        if (this.callbacks.has(evt)) {
            const handlers = this.callbacks.get(evt)!;
            handlers.forEach((handler) => {
                try {
                    handler(data);
                } catch(e: any) {
                    // TODO: What should we do with this, send to server?
                    console.log("Event handler raised exception during processing: " + e);
                    console.error(e);
                }
            });
        }

        if (this.deferreds.has(evt)) {
            const handlers = this.deferreds.get(evt)!;
            handlers.forEach((handler) => {
                try {
                    handler(data);
                } catch(e: any) {
                    // TODO: What should we do with this, send to server?
                    console.log("Event handler raised exception during processing: " + e);
                    console.error(e);
                }
            });
        }
    }

    on(evt: string, callback: HandlerCallback, deferred?: boolean): void {
        if (deferred) {
            if (!this.deferreds.has(evt)) {
                this.deferreds.set(evt, [callback]);
            } else {
                this.deferreds.get(evt)!.push(callback);
            }
        } else {
            if (!this.callbacks.has(evt)) {
                this.callbacks.set(evt, [callback]);
            } else {
                this.callbacks.get(evt)!.push(callback);
            }
        }
    }

    emit(evt: string, data: any): void {
        this._call(evt, data);
    }
}

export { EventHandler };
