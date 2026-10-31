import { describe, expect, it } from 'vitest';

import { addressProblem, deliveryErrorKey, errorField, errorKey, insertPlaceholder, parseRecipients, placeholdersFor, templateProblem } from './email-actions';

describe('recipients', () => {
    it('splits on lines, commas, semicolons and spaces and keeps each address once', () => {
        expect(parseRecipients('a@acme.example\nB@acme.example, a@ACME.example;c@acme.example  ')).toEqual(['a@acme.example', 'B@acme.example', 'c@acme.example']);
        expect(parseRecipients('  \n ')).toEqual([]);
    });

    it('accepts one plain address and nothing that is a name, a list or a header', () => {
        expect(addressProblem('owner@acme.example')).toBe(false);
        for (const bad of ['owner', 'Owner <owner@acme.example>', 'a@b@c.example', 'a@b.example,c@d.example', 'a b@c.example', '@c.example', 'a@', '"a"@c.example', 'a@b.example\r\nBcc: x@y.example']) expect(addressProblem(bad)).toBe(true);
    });
});

describe('placeholders', () => {
    it('offers the mapped names and the built-ins, and no answers block in a subject', () => {
        expect(placeholdersFor(['name'], 'body')).toEqual(['name', 'form_title', 'submitted_at', 'answers']);
        expect(placeholdersFor(['name'], 'subject')).toEqual(['name', 'form_title', 'submitted_at']);
    });

    it('finds an unknown placeholder and stray braces like the server', () => {
        const allowed = ['name', 'form_title'];
        expect(templateProblem('Hi {{name}} {{ form_title }}', allowed)).toBeNull();
        expect(templateProblem('Hi {{other}}', allowed)).toEqual({ code: 'unknown_placeholder', name: 'other' });
        expect(templateProblem('Hi {{name|upper}}', allowed)).toEqual({ code: 'invalid_placeholder' });
        expect(templateProblem('Hi {{ name', allowed)).toEqual({ code: 'invalid_placeholder' });
        expect(templateProblem('${name} {% if x %}', allowed)).toBeNull();
    });

    it('inserts a placeholder over the selection and says where the cursor goes', () => {
        expect(insertPlaceholder('Hello !', 'name', 6, 6)).toEqual({ text: 'Hello {{name}}!', cursor: 14 });
        expect(insertPlaceholder('Hello XX!', 'name', 6, 8)).toEqual({ text: 'Hello {{name}}!', cursor: 14 });
        expect(insertPlaceholder('abc', 'x', 99, 100).text).toBe('abc{{x}}');
    });
});

describe('error keys', () => {
    it('maps known codes and falls back to unknown', () => {
        expect(errorKey('recipient_not_allowed')).toBe('EMAIL_ACTIONS.ERROR.recipient_not_allowed');
        expect(errorKey('surprise')).toBe('EMAIL_ACTIONS.ERROR.unknown');
        expect(deliveryErrorKey('condition_not_met')).toBe('EMAIL_ACTIONS.DELIVERIES.ERROR.condition_not_met');
        expect(deliveryErrorKey(null)).toBe('EMAIL_ACTIONS.DELIVERIES.ERROR.unknown');
    });

    it('puts a refusal next to the part of the editor it is about', () => {
        expect(errorField('recipient_not_allowed')).toBe('recipients');
        expect(errorField('invalid_respondent_field')).toBe('respondent');
        expect(errorField('unknown_placeholder')).toBe('templates');
        expect(errorField('invalid_condition')).toBe('condition');
        expect(errorField('email_actions_off')).toBeNull();
    });
});
