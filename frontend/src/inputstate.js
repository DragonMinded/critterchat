export function InputState() {
    this.current = "empty";
    this.callbacks = [];

    this.registerStateChangeCallback = function(callback) {
        this.callbacks.push(callback);
    }

    this.setState = function(newState) {
        const changed = this.current != newState;
        this.current = newState;

        if (changed) {
            this.callbacks.forEach(function(callback) {
                callback(newState);
            });
        }
    }
}
