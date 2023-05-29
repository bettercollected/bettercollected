export class ClientSideException extends Error {
    constructor(message: string | undefined) {
        super(message);
        this.name = 'ClientSideException';
    }
}

export class ValidationException extends Error {
    constructor(message: string | undefined) {
        super(message);
        this.name = 'ValidationException';
    }
}

export class ApiException extends Error {
    constructor(message: string | undefined) {
        super(message);
        this.name = 'ApiException';
    }
}

export class JsonSerializeException extends Error {
    constructor(message: string | undefined) {
        super(message);
        this.name = 'JsonSerializeException';
    }
}

export class ReferenceException extends Error {
    constructor(message: string | undefined) {
        super(message);
        this.name = 'ReferenceException';
    }
}
