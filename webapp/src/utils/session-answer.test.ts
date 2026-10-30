// Only an explicit 401 means the session has ended; a server error or a network
// failure says nothing about it and must not sign anyone out.
import { describe, expect, it } from 'vitest';

import { isSignedOutError, readServerAuthAnswer } from './session-answer';

describe('isSignedOutError (the /auth/status poll)', () => {
    it.each([
        ['a 401', { status: 401, data: { detail: 'No user logged in.' } }],
        ['a 401 whose body was not JSON', { status: 'PARSING_ERROR', originalStatus: 401, data: 'Unauthorized', error: 'SyntaxError' }]
    ])('is true for %s', (_name, error) => {
        expect(isSignedOutError(error)).toBe(true);
    });

    it.each([
        ['a network failure', { status: 'FETCH_ERROR', error: 'TypeError: Failed to fetch' }],
        ['a timeout', { status: 'TIMEOUT_ERROR', error: 'AbortError' }],
        ['a 502 error page', { status: 'PARSING_ERROR', originalStatus: 502, data: '<html>', error: 'SyntaxError' }],
        ['a 503', { status: 503, data: {} }],
        ['a 500', { status: 500, data: {} }],
        ['a 429', { status: 429, data: {} }],
        ['a 403', { status: 403, data: {} }],
        ['no error', undefined],
        ['a string', '401']
    ])('is false for %s', (_name, error) => {
        expect(isSignedOutError(error)).toBe(false);
    });
});

describe('readServerAuthAnswer (the server-side /auth/status request)', () => {
    it('reads a user from a 200 with an id', () => {
        const user = { id: 'u1', email: 'ada@example.test', roles: [] };
        expect(readServerAuthAnswer(200, user)).toEqual({ kind: 'signed-in', user });
    });

    it('reads a 401 as signed out, whatever its body', () => {
        expect(readServerAuthAnswer(401, { detail: 'No user logged in.' })).toEqual({ kind: 'signed-out' });
        expect(readServerAuthAnswer(401, null)).toEqual({ kind: 'signed-out' });
    });

    it.each([
        ['a 502 HTML page', 502, '<html>Bad Gateway</html>'],
        ['a 503 JSON without an id', 503, { detail: 'Sign-in is temporarily unavailable.' }],
        ['a 500 without a body', 500, null],
        ['a 200 without an id', 200, {}],
        ['a 200 with an empty id', 200, { id: '' }],
        ['a 403', 403, { detail: 'Forbidden' }]
    ])('reads %s as unknown', (_name, code, body) => {
        expect(readServerAuthAnswer(code, body)).toEqual({ kind: 'unknown' });
    });
});
