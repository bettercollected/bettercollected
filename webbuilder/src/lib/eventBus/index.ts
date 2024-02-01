import { EventEmitter } from 'events';

import { EventHandler } from '@app/lib/eventBus/types';

interface EventBus {
    emit(key: string, ...args: any[]): void;

    on(key: string, handler: EventHandler): void;

    removeListener(key: string, handler: EventHandler): void;
}

class EventBusAdapter implements EventBus {
    private emitter: EventEmitter;

    constructor() {
        this.emitter = new EventEmitter();
    }

    emit(key: string, ...args: any[]): void {
        this.emitter.emit(key, ...args);
    }

    on(key: string, handler: EventHandler): void {
        this.emitter.on(key, handler);
    }

    removeListener(key: string, handler: EventHandler): void {
        this.emitter.removeListener(key, handler);
    }
}

const eventBus: EventBus = new EventBusAdapter();
export default eventBus;
