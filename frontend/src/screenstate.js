export function ScreenState() {
    this.current = "chat";
    this.callbacks = [];
    this.deferreds = [];

    this.registerStateChangeCallback = function(callback, deferred) {
        if (deferred) {
            this.deferreds.push(callback);
        } else {
            this.callbacks.push(callback);
        }
    }

    this.setState = function(newState) {
        this.current = newState;

        this.callbacks.forEach(function(callback) {
            callback(newState);
        });

        this.deferreds.forEach(function(callback) {
            callback(newState);
        });
    }
}
