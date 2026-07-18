type ScreenStateCallback = (state: string) => void;

export class ScreenState {
    current: string;
    callbacks: ScreenStateCallback[];
    deferreds: ScreenStateCallback[];

    constructor() {
        this.current = "chat";
        this.callbacks = [];
        this.deferreds = [];
    }

    registerStateChangeCallback(callback: ScreenStateCallback, deferred?: boolean): void {
        if (deferred) {
            this.deferreds.push(callback);
        } else {
            this.callbacks.push(callback);
        }
    }

    setState(newState: string): void {
        this.current = newState;

        this.callbacks.forEach(function(callback: ScreenStateCallback) {
            callback(newState);
        });

        this.deferreds.forEach(function(callback: ScreenStateCallback) {
            callback(newState);
        });
    }
}
