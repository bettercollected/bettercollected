import { EventEmitter } from 'events';

interface EventBus {
    emit(key: string): void;
    on(key: string, handler: EventHandler): void;
    removeListener(key: string, handler: EventHandler): void;
}

class EventBusAdapter implements EventBus {
    private emitter: EventEmitter;

    constructor() {
        this.emitter = new EventEmitter();
    }

    emit(key: string): void {
        this.emitter.emit(key);
    }
    on(key: string, handler: EventHandler): void {
        this.emitter.removeListener(key, handler);
    }
    removeListener(key: string, handler: EventHandler): void {
        this.emitter.removeListener(key, handler);
    }
}

const eventBus: EventBus = new EventBusAdapter();
export default eventBus;
