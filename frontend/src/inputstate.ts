type InputStateCallback = (state: string) => void;

export class InputState {
    current: string;
    callbacks: InputStateCallback[];

    constructor() {
        this.current = "empty";
        this.callbacks = [];
    }

    registerStateChangeCallback(callback: InputStateCallback): void {
        this.callbacks.push(callback);
    }

    setState(newState: string): void {
        const changed = this.current != newState;
        this.current = newState;

        if (changed) {
            this.callbacks.forEach(function(callback: InputStateCallback) {
                callback(newState);
            });
        }
    }
}
