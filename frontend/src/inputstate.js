export function InputState() {
    this.current = "empty";
    this.callbacks = [];

    this.registerStateChangeCallback = function(callback) {
        this.callbacks.push(callback);
    }

    this.setState = function(newState) {
        this.current = newState;

        this.callbacks.forEach(function(callback) {
            callback(newState);
        });
    }
}
