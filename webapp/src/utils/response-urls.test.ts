import { describe, expect, it } from 'vitest';

import { responsePageUrl } from './response-urls';

describe('responsePageUrl', () => {
    it('keeps an ordinary form and response id as they are', () => {
        expect(responsePageUrl('acme', 'f1', 'r1')).toBe('/acme/dashboard/forms/f1/responses/r1');
        expect(responsePageUrl('acme', 'f1', 'r1', 'deletion-requests')).toBe('/acme/dashboard/forms/f1/responses/r1?from=deletion-requests');
    });

    it('encodes the form id and the response id as one path segment each', () => {
        expect(responsePageUrl('acme', 'f/../x?y#z', 'r/1')).toBe('/acme/dashboard/forms/f%2F..%2Fx%3Fy%23z/responses/r%2F1');
    });
});
