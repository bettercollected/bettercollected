import { describe, expect, it } from 'vitest';

import { openFormulierenImportOn } from '@app/lib/hooks/use-open-formulieren-import-mode';
import { MAX_UPLOAD_BYTES, REPORT_REASONS, UPLOAD_ERROR_CODES, groupReport, nationalIdentityItems, plainText, reportLabelOf, reportSentenceOf, uploadProblemOf, uploadTooLarge } from '@app/utils/open-formulieren-import';

import enBuilder from '../../public/locales/en/builder.json';
import nlBuilder from '../../public/locales/nl/builder.json';

const en = (enBuilder as any).OPEN_FORMULIEREN_IMPORT;
const nl = (nlBuilder as any).OPEN_FORMULIEREN_IMPORT;

function leaves(tree: any, prefix = ''): Array<[string, string]> {
    return Object.entries(tree).flatMap(([k, v]) => (typeof v === 'object' ? leaves(v, `${prefix}${k}.`) : [[`${prefix}${k}`, v as string] as [string, string]]));
}

const valueOf = (tree: any, key: string) => key.split('.').reduce((node, part) => node?.[part], tree) as string | undefined;

describe('the providers entry', () => {
    it('is on only for an open_formulieren entry whose mode is "on"', () => {
        expect(
            openFormulierenImportOn([
                { providerName: 'google', importMode: 'on' },
                { providerName: 'open_formulieren', importMode: 'on' }
            ])
        ).toBe(true);
    });

    it('treats no entry, an unknown mode and an unreadable list as off', () => {
        expect(openFormulierenImportOn([{ providerName: 'google', importMode: 'on' }])).toBe(false);
        expect(openFormulierenImportOn([{ providerName: 'open_formulieren', importMode: 'readonly' }])).toBe(false);
        expect(openFormulierenImportOn([{ providerName: 'open_formulieren' }])).toBe(false);
        expect(openFormulierenImportOn(undefined)).toBe(false);
        expect(openFormulierenImportOn(null)).toBe(false);
        expect(openFormulierenImportOn([])).toBe(false);
    });
});

describe('the upload refusals', () => {
    it('has an English and a Dutch message for every code of the contract', () => {
        for (const code of UPLOAD_ERROR_CODES) {
            const { key } = uploadProblemOf({ status: 400, data: { code, file: 'forms.json' } });
            expect(key).toBe(`ERROR.${code}`);
            expect(valueOf(en, key), `en ${code}`).toBeTruthy();
            expect(valueOf(nl, key), `nl ${code}`).toBeTruthy();
        }
    });

    it('names the version and the supported series', () => {
        const problem = uploadProblemOf({ status: 400, data: { code: 'open_formulieren_version_unsupported', version: '4.1.2', supported: ['4.0'] } });
        expect(problem.values).toEqual({ version: '4.1.2', supported: '4.0.x' });
        expect(valueOf(en, problem.key)).toContain('{{version}}');
        expect(valueOf(en, problem.key)).toContain('{{supported}}');
        expect(valueOf(nl, problem.key)).toContain('{{version}}');
        expect(valueOf(nl, problem.key)).toContain('{{supported}}');
    });

    it('carries the size limit, the missing files and the broken file', () => {
        expect(uploadProblemOf({ status: 413, data: { code: 'file_too_large', maxBytes: 5 * 1024 * 1024 } }).values).toEqual({ mb: 5 });
        expect(uploadProblemOf({ status: 413, data: { code: 'file_too_large' } }).values).toEqual({ mb: 5 });
        expect(uploadProblemOf({ status: 400, data: { code: 'archive_incomplete', missing: ['forms.json', '_meta.json'] } }).values).toEqual({ files: 'forms.json, _meta.json' });
        expect(uploadProblemOf({ status: 400, data: { code: 'archive_json_invalid', file: 'formSteps.json' } }).values).toEqual({ file: 'formSteps.json' });
    });

    it('says "something could not be read" when the broken file is the whole archive', () => {
        for (const data of [{ code: 'archive_json_invalid', file: 'archive' }, { code: 'archive_json_invalid' }]) {
            const problem = uploadProblemOf({ status: 422, data });
            expect(problem.key).toBe('ERROR.archive_unreadable');
            expect(problem.values).toEqual({});
            expect(valueOf(en, problem.key)).toBeTruthy();
            expect(valueOf(nl, problem.key)).toBeTruthy();
            expect(valueOf(en, problem.key)).not.toContain('{{');
        }
    });

    it('maps the busy and daily-limit refusals', () => {
        expect(uploadProblemOf({ status: 503, data: { code: 'import_busy' } }).key).toBe('ERROR.import_busy');
        expect(uploadProblemOf({ status: 429, data: { code: 'import_limit' } }).key).toBe('ERROR.import_limit');
        expect(valueOf(en, 'ERROR.import_busy')).toContain('few seconds');
        expect(valueOf(en, 'ERROR.import_limit')).toContain('tomorrow');
    });

    it('keeps the items that say why nothing could be imported', () => {
        const item = { code: 'dropped', kind: 'component', reason: 'unsupported_component_type', detail: { componentType: 'signature' } };
        expect(uploadProblemOf({ status: 422, data: { code: 'no_importable_fields', reportItems: [item] } }).items).toEqual([item]);
    });

    it('says "not allowed" for a 403 and a generic line for anything else', () => {
        expect(uploadProblemOf({ status: 403, data: { detail: 'Forbidden' } }).key).toBe('ERROR.forbidden');
        expect(uploadProblemOf({ status: 500, data: 'oops' }).key).toBe('ERROR.upload_failed');
        expect(uploadProblemOf({ status: 'FETCH_ERROR', error: 'x' }).key).toBe('ERROR.upload_failed');
        expect(uploadProblemOf({ status: 400, data: { code: 'a_code_from_a_newer_server' } }).key).toBe('ERROR.upload_failed');
        expect(uploadProblemOf(undefined).key).toBe('ERROR.upload_failed');
        expect(valueOf(en, 'ERROR.forbidden')).toBeTruthy();
        expect(valueOf(nl, 'ERROR.upload_failed')).toBeTruthy();
    });

    it('knows an upload over 5 MiB is too large before sending it', () => {
        expect(uploadTooLarge({ size: MAX_UPLOAD_BYTES })).toBe(false);
        expect(uploadTooLarge({ size: MAX_UPLOAD_BYTES + 1 })).toBe(true);
    });
});

describe('the report sentences', () => {
    it('has an English and a Dutch sentence for every reason of the contract', () => {
        for (const reason of REPORT_REASONS) {
            const { key } = reportSentenceOf({ code: 'dropped', reason });
            expect(key).toBe(`REASON.${reason}`);
            expect(valueOf(en, key), `en ${reason}`).toBeTruthy();
            expect(valueOf(nl, key), `nl ${reason}`).toBeTruthy();
        }
    });

    it('uses a generic line for a reason it does not know, by what happened to the item', () => {
        for (const code of ['dropped', 'changed', 'flagged', 'ignored']) {
            const { key } = reportSentenceOf({ code, reason: 'a_reason_from_a_newer_server' });
            expect(key).toBe(`REASON_FALLBACK.${code}`);
            expect(valueOf(en, key)).toBeTruthy();
            expect(valueOf(nl, key)).toBeTruthy();
        }
        expect(reportSentenceOf({ code: 'something_new', reason: 'x' }).key).toBe('REASON_FALLBACK.other');
    });

    it('takes only the known detail keys, as short plain text', () => {
        const { values } = reportSentenceOf({ code: 'dropped', reason: 'unsupported_component_type', detail: { componentType: 'signature\nx', evil: '<img onerror=x>', plugin: 'a'.repeat(500), count: 3 } });
        expect(values.componentType).toBe('signature x');
        expect(values.plugin).toHaveLength(80);
        expect(values).not.toHaveProperty('evil');
        expect(values).not.toHaveProperty('count');
    });

    it('is plain language: every sentence is 20 words or fewer, in both languages', () => {
        for (const [name, tree] of [
            ['en', en],
            ['nl', nl]
        ] as const) {
            const sentences = leaves(tree).filter(([key]) => key.startsWith('REASON') || key.startsWith('ERROR.'));
            for (const [key, text] of sentences) {
                // a message may hold several sentences; each is judged alone
                for (const sentence of text.split(/(?<=[.!?])\s+/)) {
                    const words = sentence
                        .replace(/\{\{[^}]+\}\}/g, 'x')
                        .split(/\s+/)
                        .filter(Boolean).length;
                    expect(words, `${name} ${key}: ${sentence}`).toBeLessThanOrEqual(20);
                }
            }
        }
    });

    it('has the same keys in both languages', () => {
        expect(
            leaves(nl)
                .map(([key]) => key)
                .sort()
        ).toEqual(
            leaves(en)
                .map(([key]) => key)
                .sort()
        );
    });

    it('never names the government or the national identity number by its short name', () => {
        const everything = JSON.stringify([en, nl]).toLowerCase();
        for (const word of ['bsn', 'burgerservicenummer', 'municipal', 'gemeente', 'overheid', 'government']) expect(everything).not.toContain(word);
    });

    it('says the national identity number line as the contract words it', () => {
        expect(en.REPORT.ID_TITLE).toBe('National identity number: check you need it.');
        expect(nl.REPORT.ID_TITLE).toContain('Nationaal identificatienummer');
    });
});

describe('grouping and flags', () => {
    const items = [
        { code: 'dropped', kind: 'component', reason: 'always_hidden', key: 'a' },
        { code: 'flagged', kind: 'component', reason: 'national_identity_number', flag: 'national_identity_number', key: 'bsn', label: 'ID' },
        { code: 'ignored', kind: 'archive', reason: 'archive_entry_ignored', key: 'x.txt' },
        { code: 'dropped', kind: 'logic', reason: 'target_missing', key: 'rule-1' },
        { code: 'brand_new', kind: 'component', reason: 'y' }
    ];

    it('lists what to check first, then what was left out, keeping the server order inside a group', () => {
        const groups = groupReport(items);
        expect(groups.map((g) => g.code)).toEqual(['flagged', 'dropped', 'ignored', 'other']);
        expect(groups[1].items.map((i) => i.key)).toEqual(['a', 'rule-1']);
    });

    it('puts advisories in their own group and orders questions by page, then rules, features and settings', () => {
        const mixed = [
            { code: 'dropped', kind: 'setting', key: 's', reason: 'retention_other_limits_not_carried' },
            { code: 'dropped', kind: 'feature', key: 'f', reason: 'payment_not_carried' },
            { code: 'dropped', kind: 'logic', key: 'rule-1', reason: 'target_missing' },
            { code: 'dropped', kind: 'component', key: 'c3', reason: 'always_hidden', step: 2 },
            { code: 'dropped', kind: 'component', key: 'c1', reason: 'always_hidden', step: 0 },
            { code: 'dropped', kind: 'component', key: 'c2', reason: 'always_hidden', step: 1 },
            { code: 'noted', kind: 'setting', key: 'purpose', reason: 'purpose_missing' }
        ];
        const groups = groupReport(mixed);
        expect(groups.map((g) => g.code)).toEqual(['dropped', 'noted']);
        expect(groups[0].items.map((i) => i.key)).toEqual(['c1', 'c2', 'c3', 'rule-1', 'f', 's']);
    });

    it('finds the national identity number items', () => {
        expect(nationalIdentityItems(items).map((i) => i.key)).toEqual(['bsn']);
        expect(nationalIdentityItems([])).toEqual([]);
    });

    it('labels an item by its label, else by the key of a question or variable only', () => {
        expect(reportLabelOf({ kind: 'component', label: 'Signature', key: 'sig' })).toBe('Signature');
        expect(reportLabelOf({ kind: 'component', key: 'sig' })).toBe('sig');
        expect(reportLabelOf({ kind: 'variable', key: 'total' })).toBe('total');
        for (const kind of ['setting', 'feature', 'logic', 'archive']) expect(reportLabelOf({ kind, key: 'purpose' })).toBe('');
        expect(reportLabelOf({ kind: 'setting', label: 'Privacy policy', key: 'privacy' })).toBe('Privacy policy');
    });

    it('cleans text from the server', () => {
        expect(plainText('a\u0000b\tc')).toBe('a b c');
        expect(plainText(undefined)).toBe('');
        expect(plainText('x'.repeat(300), 10)).toHaveLength(10);
    });
});
