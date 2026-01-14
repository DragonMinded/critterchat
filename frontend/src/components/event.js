/**
 * Handles providing a simple event broadcaster and listener interface. Originally
 * based on npm's event library, but that was way too much code for such a simple
 * functionality so this was written in its stead.
 */
class EventHandler {
    constructor() {
        this.callbacks = new Map();
    }

    _call( evt, data ) {
        if (this.callbacks.has(evt)) {
            const handlers = this.callbacks.get(evt);
            handlers.forEach((handler) => {
                try {
                    handler(data);
                } catch(e) {
                    // TODO: What should we do with this, send to server?
                    console.log("Event handler raised exception during processing: " + e);
                    console.log(e);
                }
            });
        }
    }

    on( evt, callback ) {
        if (!this.callbacks.has(evt)) {
            this.callbacks.set(evt, [callback]);
        } else {
            this.callbacks.get(evt).push(callback);
        }
    }

    emit( evt, data ) {
        this._call(evt, data);
    }
}

export { EventHandler };
