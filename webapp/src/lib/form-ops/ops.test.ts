import { describe, expect, it } from 'vitest';

import { idMaker, smallForm } from './__fixtures__/forms';
import { applied, applyOps, tooManyOps } from './apply';
import { MAX_PAGES, locateField } from './model';
import { refDependencies } from './refs';
import type { FormDoc, FormOp } from './types';

const run = (ops: FormOp[] | any[], doc: FormDoc = smallForm(), atomic = false) => applyOps(doc, ops as FormOp[], { atomic, newId: idMaker() });
const field = (doc: FormDoc, id: string) => locateField(doc, id).field;
const one = (op: any, doc?: FormDoc) => {
    const out = run([op], doc);
    return { ...out, result: out.results[0] };
};

describe('add_field', () => {
    it('adds a question at an index, renumbered, with the backend message', () => {
        const { doc, result } = one({ op: 'add_field', pageId: 'p2', index: 1, field: { title: 'Email', type: 'email', required: true, whyWeAsk: '  to reply  ' } });
        expect(result).toEqual({ index: 0, op: 'add_field', ok: true, message: "Added 'Email' (email) to page 2", createdId: 'new-1' });
        const added = doc.fields[1].properties!.fields![1];
        expect(added).toEqual({ id: 'new-1', index: 1, type: 'email', title: 'Email', properties: { fields: [], whyWeAsk: 'to reply' }, validations: { required: true } });
        expect(doc.fields[1].properties!.fields![2].index).toBe(2);
    });

    it('builds choices, yes/no and ratings like the builder', () => {
        const { doc } = run([
            { op: 'add_field', pageId: 'p3', field: { title: 'Pick', type: 'multiple_choice', choices: ['A', 'B'], allowMultiple: true } },
            { op: 'add_field', pageId: 'p3', field: { title: 'Ok?', type: 'yes_no' } },
            { op: 'add_field', pageId: 'p3', field: { title: 'Rate', type: 'linear_rating' } }
        ]);
        const [, pick, ok, rate] = doc.fields[2].properties!.fields!;
        expect(pick.properties!.choices).toEqual([
            { id: 'new-1', value: 'A' },
            { id: 'new-2', value: 'B' }
        ]);
        expect(pick.properties!.allowMultipleSelection).toBe(true);
        expect(ok.properties!.choices!.map((c) => c.value)).toEqual(['Yes', 'No']);
        expect(rate.properties!.steps).toBe(10);
    });

    it('adds into a repeating group and refuses what a group cannot hold', () => {
        const { doc, result } = one({ op: 'add_field', groupId: 'kids', afterFieldId: 'kid-name', field: { title: 'School', type: 'short_text' } });
        expect(result.message).toBe("Added 'School' (short_text) to the group 'Children'");
        expect(field(doc, 'kids').properties!.fields!.map((f) => f.id)).toEqual(['kid-name', 'new-1', 'kid-born', 'kid-yes']);
        expect(one({ op: 'add_field', groupId: 'kids', field: { title: 'Up', type: 'file_upload' } }).result.message).toBe(
            "A 'file_upload' question cannot be placed inside a repeating group (allowed: date, dropdown, email, linear_rating, long_text, multiple_choice, number, phone_number, rating, short_text, text, url, yes_no)."
        );
        expect(one({ op: 'add_field', groupId: 'name', field: { title: 'x', type: 'short_text' } }).result.message).toBe("'Your name' is not a repeating group.");
    });

    it('reports the errors of the backend', () => {
        expect(one({ op: 'add_field', field: { title: 'x', type: 'email' } }).result.message).toBe('add_field needs a pageId (or a groupId to add into a repeating group).');
        expect(one({ op: 'add_field', pageId: 'nope', field: { title: 'x', type: 'email' } }).result.message).toBe("Page 'nope' was not found — it may have been removed.");
        expect(one({ op: 'add_field', pageId: 'p1', field: { title: 'x', type: 'matrix' } }).result.message).toBe(
            "Field type 'matrix' cannot be created by AI ops (allowed: calculated, date, dropdown, email, file_upload, linear_rating, long_text, multiple_choice, number, phone_number, rating, short_text, text, url, yes_no)."
        );
        expect(one({ op: 'add_field', pageId: 'p1', field: { title: 'x', type: 'dropdown', choices: ['one'] } }).result.message).toBe("'dropdown' needs at least 2 choices.");
        expect(one({ op: 'add_field', pageId: 'p1', afterFieldId: 'age', field: { title: 'x', type: 'email' } }).result.message).toBe("Field 'age' is not in page 'p1'.");
        expect(one({ op: 'add_field', pageId: 'p1', field: { title: 'x', type: 'email', label: 'L' } }).result.message).toBe('A label only applies to date questions.');
        expect(one({ op: 'add_field', pageId: 'p1', field: { title: 'x', type: 'file_upload', internal: true } }).result.message).toMatch(/^'file_upload' fields can't be internal/);
    });
});

describe('update_field', () => {
    it('patches and lists the changes', () => {
        const { doc, result } = one({ op: 'update_field', fieldId: 'name', patch: { title: 'Full name', required: false, colSpan: 6, placeholder: 'Jane' } });
        expect(result.message).toBe("Updated 'Full name' (title, optional, placeholder, width)");
        expect(field(doc, 'name')).toMatchObject({ title: 'Full name', validations: { required: false }, properties: { colSpan: 6, placeholder: 'Jane' } });
    });

    it('keeps the ids of choices whose label stays', () => {
        const { doc } = one({ op: 'update_field', fieldId: 'color', patch: { choices: ['Blue', 'Purple', 'Red'] } });
        expect(field(doc, 'color').properties!.choices).toEqual([
            { id: 'c-blue', value: 'Blue' },
            { id: 'new-1', value: 'Purple' },
            { id: 'c-red', value: 'Red' }
        ]);
    });

    it('takes a rich-text title', () => {
        const title = { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Hi' }] }] };
        const { doc, result } = one({ op: 'update_field', fieldId: 'bio', patch: { title } });
        expect(field(doc, 'bio').title).toEqual(title);
        expect(result.message).toBe("Updated 'bio' (title)");
    });

    it('updates repeat settings and checks them', () => {
        expect(one({ op: 'update_field', fieldId: 'kids', patch: { maxItems: 6, itemTitle: 'Child {{field:kid-name}}' } }).result.message).toBe("Updated 'Children' (max items, item title)");
        expect(one({ op: 'update_field', fieldId: 'kids', patch: { minItems: 5, maxItems: 2 } }).result.message).toBe("A repeating group's minimum number of items cannot exceed its maximum.");
        expect(one({ op: 'update_field', fieldId: 'kids', patch: { maxItems: 51 } }).result.message).toBe('Input should be less than or equal to 50');
        expect(one({ op: 'update_field', fieldId: 'name', patch: { maxItems: 3 } }).result.message).toBe('Item limits and labels only apply to repeating groups.');
    });

    it('guards internal fields and date rules', () => {
        expect(one({ op: 'update_field', fieldId: 'color', patch: { internal: true } }).result.message).toMatch(/^'Favourite colour' is used by conditional logic/);
        expect(one({ op: 'update_field', fieldId: 'start', patch: { internal: true } }).result.message).toMatch(/^'Start date' is used by a date rule/);
        expect(one({ op: 'update_field', fieldId: 'kid-name', patch: { internal: true } }).result.message).toMatch(/^Internal fields cannot be placed inside a repeating group/);
        expect(one({ op: 'update_field', fieldId: 'start', patch: { dateRules: [{ comparison: 'before', target: 'field', fieldId: 'end' }] } }).result.message).toBe(
            "Date rules cannot depend on each other in a circle ('Start date' → 'End date' → 'Start date')."
        );
        expect(one({ op: 'update_field', fieldId: 'start', patch: { dateRules: [{ comparison: 'before', target: 'date', date: '2026-02-30' }] } }).result.message).toBe('A date rule needs a date written as YYYY-MM-DD.');
        const ok = one({ op: 'update_field', fieldId: 'start', patch: { dateRules: [{ comparison: 'after', target: 'today', date: '2020-01-01' }], label: ' From ' } });
        expect(field(ok.doc, 'start').properties).toMatchObject({ dateRules: [{ comparison: 'after', target: 'today' }], label: 'From' });
        expect(one({ op: 'update_field', fieldId: 'name', patch: { dateRules: [] } }).result.message).toBe('Date rules only apply to date questions.');
    });

    it('keeps what was patched before a failing key, like the backend', () => {
        const { doc, result } = one({ op: 'update_field', fieldId: 'name', patch: { title: 'Changed', steps: 3 } });
        expect(result.ok).toBe(false);
        expect(result.message).toBe("'steps' only applies to rating fields.");
        expect(field(doc, 'name').title).toBe('Changed');
    });

    it('refuses an empty patch', () => {
        expect(one({ op: 'update_field', fieldId: 'name', patch: {} }).result.message).toBe('The update contained no changes.');
        expect(one({ op: 'update_field', fieldId: 'nope', patch: { title: 'x' } }).result.message).toBe("Field 'nope' was not found — it may have been removed.");
    });
});

describe('remove_field and move_field', () => {
    it('removes a question and the date rules that used it', () => {
        const { doc, result } = one({ op: 'remove_field', fieldId: 'start' });
        expect(result.message).toBe("Removed 'Start date' (and 1 date rule(s) that used it)");
        expect(field(doc, 'end').properties!.dateRules).toBeUndefined();
    });

    it('moves within a page, to another page and into or out of a group', () => {
        expect(one({ op: 'move_field', fieldId: 'name', index: 2 }).result.message).toBe("Moved 'Your name' to position 3");
        const toPage = one({ op: 'move_field', fieldId: 'bio', toPageId: 'p1', index: 0 });
        expect(toPage.result.message).toBe("Moved 'About you' to page 1");
        expect(toPage.doc.fields[0].properties!.fields!.map((f) => f.id).slice(0, 2)).toEqual(['bio', 'name']);
        const intoGroup = one({ op: 'move_field', fieldId: 'end', toGroupId: 'kids' });
        expect(intoGroup.result.message).toBe("Moved 'End date' to the group 'Children' (and 1 date rule(s) that used it)");
        const outOfGroup = one({ op: 'move_field', fieldId: 'kid-name', toPageId: 'p2' });
        expect(outOfGroup.result.message).toBe("Moved 'Name' to page 2");
        expect(one({ op: 'move_field', fieldId: 'kid-born', index: 0 }).result.message).toBe("Moved 'Born' to position 1");
        expect(one({ op: 'move_field', fieldId: 'kids', toGroupId: 'kids' }).result.message).toBe('A group cannot be moved into itself.');
    });
});

describe('pages', () => {
    it('adds, removes and moves pages', () => {
        const added = one({ op: 'add_page', index: 1, fields: [{ title: 'Q', type: 'number' }] });
        expect(added.result.message).toBe('Added a page with 1 field(s)');
        expect(added.doc.fields.map((p) => p.id)).toEqual(['p1', 'new-2', 'p2', 'p3']);
        expect(added.doc.fields[1]).toMatchObject({ index: 1, type: 'slide', properties: { layout: 'SINGLE_COLUMN_NO_BACKGROUND' } });
        expect(one({ op: 'remove_page', pageId: 'p1' }).result.message).toBe('Removed a page (5 field(s) with it) (and 1 logic or piping reference(s) to it)');
        const moved = one({ op: 'move_page', pageId: 'p3', index: 0 });
        expect(moved.result.message).toBe('Moved page 3 to position 1');
        expect(moved.doc.fields.map((p) => [p.id, p.index])).toEqual([
            ['p3', 0],
            ['p1', 1],
            ['p2', 2]
        ]);
        expect(one({ op: 'move_page', pageId: 'p2', index: 1 }).result.message).toBe('Page 2 stays at position 2');
        expect(one({ op: 'move_page', pageId: 'p2', index: -1 }).result.message).toBe("A page's new position (index) must be 0 or more.");
    });

    it('duplicates a page with fresh ids and in-page references remapped', () => {
        const { doc, result } = one({ op: 'duplicate_page', pageId: 'p1' });
        expect(result.message).toBe("Duplicated page 'p1' (5 fields) as 'new-1'");
        const copy = doc.fields[1];
        expect(copy.id).toBe('new-1');
        expect(copy.properties!.jumps).toBeUndefined();
        const [, , start, end] = copy.properties!.fields!;
        expect(end.properties!.dateRules![0].fieldId).toBe(start.id);
        expect(start.id).not.toBe('start');
    });

    it('sets page jumps and visibility rules with checked conditions', () => {
        const jumps = one({ op: 'set_page_jumps', pageId: 'p1', jumps: [{ target: '__SUBMIT__', conditions: [{ fieldId: 'color', comparison: 'IS_EQUAL', value: 'Blue' }] }] });
        expect(jumps.result.message).toBe("Set 1 jump rule(s) on page 'p1'");
        expect(jumps.doc.fields[0].properties!.jumps).toEqual([{ operator: 'AND', target: '__SUBMIT__', conditions: [{ fieldId: 'color', fieldType: 'multiple_choice', comparison: 'IS_EQUAL', value: 'Blue' }] }]);
        expect(one({ op: 'set_page_jumps', pageId: 'p1', jumps: [{ target: 'p1', conditions: [{ fieldId: 'name', comparison: 'IS_EMPTY' }] }] }).result.message).toBe('A page cannot jump to itself.');
        expect(one({ op: 'set_page_jumps', pageId: 'p1', jumps: null }).result.message).toBe("Cleared page jumps on page 'p1'");

        const logic = one({ op: 'set_field_logic', fieldId: 'bio', logic: { action: 'HIDE', conditions: [{ fieldId: 'kids', comparison: 'GREATER_THAN', value: '2', groupMode: 'COUNT' }] } });
        expect(logic.result.message).toBe("Hide 'About you' when 1 condition(s) match");
        expect(field(logic.doc, 'bio').properties!.logic).toEqual({ action: 'HIDE', operator: 'AND', conditions: [{ fieldId: 'kids', fieldType: 'group', comparison: 'GREATER_THAN', value: 2, groupMode: 'COUNT' }] });
        expect(one({ op: 'set_field_logic', fieldId: 'bio', logic: { action: 'SHOW', conditions: [{ fieldId: 'color', comparison: 'IS_EQUAL', value: 'Pink' }] } }).result.message).toBe(
            "'Pink' is not a choice of 'Favourite colour'. Choices: Red, Blue, Green"
        );
        expect(one({ op: 'set_field_logic', fieldId: 'bio', logic: { action: 'SHOW', conditions: [{ fieldId: 'kid-name', comparison: 'IS_EMPTY' }] } }).result.message).toMatch(/is asked once per item of 'Children'/);
        expect(one({ op: 'set_field_logic', fieldId: 'kid-born', logic: { action: 'SHOW', conditions: [{ fieldId: 'kid-yes', comparison: 'IS_EQUAL', value: 'Yes' }] } }).result.ok).toBe(true);
        expect(one({ op: 'set_field_logic', fieldId: 'bio', logic: { action: 'SHOW', conditions: [{ fieldId: 'bio', comparison: 'IS_EMPTY' }] } }).result.message).toBe("A field's visibility cannot depend on its own answer.");
    });

    it('sets and clears section titles', () => {
        const set = one({ op: 'set_section_title', pageIndex: 1, title: '  About \n you ' });
        expect(set.result.message).toBe("Section title of page 2: 'About you'");
        expect(set.doc.fields[1].properties!.sectionTitle).toBe('About you');
        const cleared = one({ op: 'set_section_title', pageId: 'p3', title: null });
        expect(cleared.doc.fields[2].properties!.sectionTitle).toBeUndefined();
        expect(one({ op: 'set_section_title', pageId: 'welcome', title: 'x' }).result.message).toBe('Only question pages have a section title; the welcome page has none. Change the form title instead.');
        expect(one({ op: 'set_section_title', pageId: 'name', title: 'x' }).result.message).toBe("'Your name' is a question, not a page: use the id of the page it is on.");
        expect(one({ op: 'set_section_title', pageId: 'p1' }).result.message).toBe('set_section_title needs a "title" (null or "" clears it).');
    });

    it('numbers questions', () => {
        const { doc, result } = one({ op: 'set_question_numbering', show: true });
        expect(result.message).toBe('Turned question numbers on for every page');
        expect(doc.fields.every((p) => p.properties!.showQuestionNumbers)).toBe(true);
    });
});

describe('answer rules', () => {
    it('sets, checks and clears rules', () => {
        const set = one({ op: 'set_field_validation', fieldId: 'name', validation: { minLength: 2, maxLength: 40, preset: 'letters' } });
        expect(set.result.message).toBe("Updated the answer rules of 'Your name' (minimum length, maximum length, pattern (letters))");
        expect(field(set.doc, 'name').validations).toEqual({ required: true, minLength: 2, maxLength: 40, regex: "^[A-Za-zÀ-ɏ' -]+$" });
        expect(one({ op: 'set_field_validation', fieldId: 'age', validation: { minValue: 10.5, maxValue: 2 } }).result.message).toBe('The minimum (10.5) cannot be more than the maximum (2).');
        expect(one({ op: 'set_field_validation', fieldId: 'age', validation: { minLength: 1 } }).result.message).toBe("Text lengths only apply to short or long text questions; 'Age' is a number question.");
        expect(one({ op: 'set_field_validation', fieldId: 'color', validation: { maxChoices: 4 } }).result.message).toBe("'Favourite colour' has 3 choice(s), so the maximum choices cannot be 4.");
        expect(one({ op: 'set_field_validation', fieldId: 'name', validation: { pattern: '(' } }).result.message).toMatch(/^'\(' is not a valid pattern/);
        // a shape that can take a browser exponential time is refused with the server's words
        expect(one({ op: 'set_field_validation', fieldId: 'name', validation: { pattern: '^(a+)+$' } }).result.message).toBe(
            'A repeated group inside a repeated group, such as (a+)+, can take a browser very long to check. Make each repeat end in a separator or use one repeat.'
        );
        expect(one({ op: 'set_field_validation', fieldId: 'name', validation: { pattern: '(a)\\1' } }).result.message).toMatch(/^A pattern cannot refer back/);
        expect(one({ op: 'set_field_validation', fieldId: 'name', validation: { pattern: '^[a-z]+( [a-z]+)*$' } }).result.message).toMatch(/^Updated the answer rules/);
        expect(one({ op: 'set_field_validation', fieldId: 'name', validation: {} }).result.message).toMatch(/^Nothing to change/);
        const cleared = one({ op: 'set_field_validation', fieldId: 'name', validation: { required: null } });
        expect(cleared.result.message).toBe("Updated the answer rules of 'Your name' (optional)");
        expect(field(cleared.doc, 'name').validations).toEqual({});
    });
});

describe('form-level ops', () => {
    it('updates the title of the form and its welcome page', () => {
        const { doc, result } = one({ op: 'update_form_info', title: 'Renamed' });
        expect(result.message).toBe('Updated form title');
        expect([doc.title, doc.welcomePage!.title]).toEqual(['Renamed', 'Renamed']);
    });

    it('checks settings and writes them like apply_settings_ops', () => {
        const { doc, result } = one({ op: 'update_form_settings', patch: { purpose: '  ', retentionText: ' 90 days ', showSubmissionNumber: true } });
        expect(result.message).toBe('Updated form settings: purpose, internal retention note, submission numbers');
        expect(doc.settings).toMatchObject({ retentionText: '90 days', showSubmissionNumber: true });
        expect((doc.settings as any).purpose).toBeUndefined();
        expect(one({ op: 'update_form_settings', patch: { privacyPolicyUrl: 'javascript:alert(1)' } }).result.message).toBe('The privacy policy link must be an http(s) URL.');
        const untouched = applyOps(smallForm(), [{ op: 'update_form_settings', patch: { purpose: 'x' } }], { applySettings: false });
        expect(untouched.results[0].ok).toBe(true);
        expect((untouched.doc.settings as any).purpose).toBe('Research');
    });

    it('applies presets by name, legacy names included, and keeps the style', () => {
        const ocean = one({ op: 'set_theme_preset', name: ' blue ' });
        expect(ocean.result.message).toBe("Applied the 'Ocean' theme");
        const leaflet = one({ op: 'set_theme_preset', name: 'Leaflet' });
        expect(leaflet.result.message).toBe("Applied the 'Leaflet' theme in the leaflet style");
        const styled = run([
            { op: 'set_theme_preset', name: 'Leaflet' },
            { op: 'set_theme_preset', name: 'Mint' }
        ]);
        expect(styled.doc.theme!.style).toBe('leaflet');
        expect(one({ op: 'set_theme_preset', name: 'Mint', style: 'fancy' }).result.message).toBe("There is no style named 'fancy'. Pick one of: classic, sheet, studio, leaflet.");
        expect(one({ op: 'set_theme_preset', name: 'Nope' }).result.message).toMatch(/^There is no theme preset named 'Nope'. Pick one of: Default, Paper, Leaflet, Ocean/);
        expect(one({ op: 'update_theme', theme: { title: 'Mine', primary: '#000', secondary: '#111', tertiary: '#222', accent: '#fff' } }).result.message).toBe("Applied theme 'Mine'");
    });

    it('checks type, shape and highlight and keeps them across colour presets', () => {
        const colours = { title: 'Mine', primary: '#16261F', secondary: '#1E4D3B', tertiary: '#7D8C84', accent: '#F8EEEC' };
        const typed = run([
            { op: 'update_theme', theme: { ...colours, titleFont: 'besley', bodyFont: 'atkinson-next', radius: 'soft', buttonStyle: 'pill', highlight: '#A3305A' } },
            { op: 'set_theme_preset', name: 'Mint' }
        ]);
        expect(typed.results.every((r) => r.ok)).toBe(true);
        expect(typed.doc.theme).toMatchObject({ title: 'Mint', titleFont: 'besley', bodyFont: 'atkinson-next', radius: 'soft', buttonStyle: 'pill' });
        expect(typed.doc.theme!.highlight).toBeUndefined();
        // null means absent, as stored forms send it
        expect(one({ op: 'update_theme', theme: { ...colours, titleFont: null, highlight: null } as any }).result.ok).toBe(true);
        expect(one({ op: 'update_theme', theme: { ...colours, titleFont: 'Comic Sans' } as any }).result.message).toBe('theme.titleFont must be one of: public-sans, atkinson-next, archivo, besley, rubik, atkinson-mono.');
        expect(one({ op: 'update_theme', theme: { ...colours, highlight: '#a3305a80' } }).result.message).toBe('theme.highlight must be a 6-digit hex colour, e.g. #A3305A.');
    });
});

describe('editor ops', () => {
    it('inserts, replaces and updates entities losslessly', () => {
        const inserted = one({ op: 'insert_field', pageId: 'p2', index: 0, field: { id: 'x1', index: 7, type: 'short_text', title: 'X', properties: { fields: [] } } });
        expect(inserted.result.message).toBe("Inserted 'X' (short_text) into page 2");
        expect(inserted.doc.fields[1].properties!.fields![0]).toEqual({ id: 'x1', index: 0, type: 'short_text', title: 'X', properties: { fields: [] } });
        expect(one({ op: 'insert_field', pageId: 'p2', index: 0, field: { id: 'name', index: 0, type: 'short_text', title: 'Dup' } }).result.message).toBe("The id 'name' is already used in this form.");
        const replaced = one({ op: 'replace_field', field: { id: 'bio', index: 0, type: 'short_text', title: 'Short bio' } });
        expect(field(replaced.doc, 'bio')).toEqual({ id: 'bio', index: 1, type: 'short_text', title: 'Short bio' });
        const page = one({ op: 'insert_page', index: 0, page: { id: 'p0', index: 0, type: 'slide', properties: { fields: [{ id: 'q0', index: 0, type: 'email', title: 'Mail' }] } } });
        expect(page.result.message).toBe('Inserted a page with 1 field(s) at position 1');
        expect(page.doc.fields.map((p) => p.id)).toEqual(['p0', 'p1', 'p2', 'p3']);
        const updated = one({ op: 'update_page', pageId: 'p3', patch: { sectionTitle: null, layout: 'TWO_COLUMN_IMAGE_LEFT' } });
        expect(updated.result.message).toBe('Updated page 3 (layout, section title)');
        expect(updated.doc.fields[2].properties).toEqual({ fields: updated.doc.fields[2].properties!.fields, layout: 'TWO_COLUMN_IMAGE_LEFT' });
        expect(one({ op: 'update_page', pageId: 'p3', patch: { jumps: [] } }).result.message).toBe('patch.jumps: Extra inputs are not permitted');
    });

    it('checks what it takes like a whole-form save', () => {
        const foreign = one({ op: 'insert_field', pageId: 'p1', index: 0, field: { id: 'img', type: 'short_text', title: 'I', imageUrl: 'https://images.example.org/x.png' } });
        expect(foreign.result.message).toMatch(/^Images must come from/);
        const storage = applyOps(smallForm(), [{ op: 'insert_field', pageId: 'p1', index: 0, field: { id: 'img', index: 0, type: 'short_text', title: 'I', imageUrl: 'https://files.example.org/bucket/public/x.png' } as any }], {
            isStorageImageUrl: (url) => url.startsWith('https://files.example.org/bucket/public/')
        });
        expect(storage.results[0].ok).toBe(true);
        expect(one({ op: 'insert_field', groupId: 'kids', index: 0, field: { id: 'up', type: 'file_upload', title: 'Up' } }).result.message).toMatch(/cannot be placed inside a repeating group/);
        expect(one({ op: 'replace_field', field: { id: 'p2', type: 'slide' } }).result.message).toBe('A page is not a question: use insert_page or update_page.');
    });

    it('edits choices by id', () => {
        const { doc, results } = run([
            { op: 'set_choice', fieldId: 'color', choiceId: 'c-red', value: 'Crimson' },
            { op: 'add_choice', fieldId: 'color', choice: { id: 'c-pink', value: 'Pink' }, index: 0 },
            { op: 'remove_choice', fieldId: 'color', choiceId: 'c-green' },
            { op: 'move_choice', fieldId: 'color', choiceId: 'c-blue', index: 0 }
        ]);
        expect(results.map((r) => r.message)).toEqual(["Changed a choice of 'Favourite colour'", "Added a choice to 'Favourite colour'", "Removed a choice of 'Favourite colour'", "Moved a choice of 'Favourite colour' to position 1"]);
        expect(field(doc, 'color').properties!.choices).toEqual([
            { id: 'c-blue', value: 'Blue' },
            { id: 'c-pink', value: 'Pink' },
            { id: 'c-red', value: 'Crimson' }
        ]);
        expect(one({ op: 'add_choice', fieldId: 'kid-yes', choice: { id: 'm', value: 'Maybe' } }).result.message).toBe('Yes/No choices are fixed.');
        expect(one({ op: 'move_choice', fieldId: 'kid-yes', choiceId: 'y2', index: 0 }).result.ok).toBe(true);
    });

    it('sets the welcome page, hidden fields and logo', () => {
        const { doc, results } = run([
            { op: 'update_welcome_page', patch: { description: null, buttonText: 'Begin' } },
            { op: 'set_hidden_fields', names: ['utm_source', 'campaign'] },
            { op: 'update_logo', alt: 'Our logo', position: 'center' }
        ]);
        expect(results.map((r) => r.message)).toEqual(['Updated the welcome page (description, button text)', 'Set 2 hidden field(s)', 'Updated the logo settings (alt text, position)']);
        expect(doc.welcomePage).toEqual({ title: 'Intake', buttonText: 'Begin' });
        expect(doc.hiddenFields).toEqual(['utm_source', 'campaign']);
        expect([doc.logoAlt, doc.logoPosition]).toEqual(['Our logo', 'center']);
        expect(one({ op: 'set_hidden_fields', names: ['a b'] }).result.ok).toBe(true);
        expect(one({ op: 'set_hidden_fields', names: ['x'.repeat(201)] }).result.message).toBe('A hidden field name can be at most 200 characters.');
    });
});

describe('removal and titles', () => {
    it('keeps jumps to a removed page and counts only what the op removed', () => {
        const { doc, result } = one({ op: 'remove_page', pageId: 'p3' });
        expect(result.message).toBe('Removed a page (1 field(s) with it)');
        expect(doc.fields[0].properties!.jumps).toEqual(smallForm().fields[0].properties!.jumps);
    });

    it('takes only titles the title editor can render', () => {
        const title = (content: any[]) => ({ op: 'update_field', fieldId: 'bio', patch: { title: { type: 'doc', content } } });
        expect(one(title([{ type: 'paragraph', content: [{ type: 'text', text: 'Hi', marks: [{ type: 'bold' }] }] }])).result.ok).toBe(true);
        expect(one(title([{ type: 'image', attrs: { src: 'x' } }])).result.message).toBe("A rich-text title cannot hold a 'image' node.");
        expect(one(title([{ type: 'paragraph', content: [{ type: 'text', text: 'a', marks: [{ type: 'link' }] }] }])).result.message).toBe("A rich-text title cannot use a 'link' mark.");
        expect(one(title([{ type: 'heading', attrs: { level: 9 } }])).result.message).toBe("A heading's level must be 1 to 6.");
    });

    it('refuses editor ops and rich-text titles outside the editor', () => {
        const out = applyOps(
            smallForm(),
            [
                { op: 'set_hidden_fields', names: [] },
                { op: 'update_field', fieldId: 'bio', patch: { title: { type: 'doc', content: [] } } }
            ],
            { editor: false }
        );
        expect(out.results.map((r) => r.message)).toEqual(["The operation 'set_hidden_fields' is only available in the form editor; it cannot be used here.", 'A title must be plain text here; rich-text titles come only from the form editor.']);
    });
});

describe('batches', () => {
    it('resolves client references, and reports a failed definer', () => {
        const { doc, results } = run([
            { op: 'add_page', ref: 'pg', fields: [{ title: 'A', type: 'yes_no', ref: 'a' }] },
            { op: 'add_field', pageId: '$ref:pg', field: { title: 'B', type: 'short_text' } },
            { op: 'set_field_logic', fieldId: '$ref:b-missing', logic: null },
            { op: 'add_field', pageId: 'nope', ref: 'gone', field: { title: 'C', type: 'short_text' } },
            { op: 'remove_field', fieldId: '$ref:gone' },
            { op: 'set_page_jumps', pageId: 'p1', jumps: [{ target: '$ref:pg', conditions: [{ fieldId: '$ref:a', comparison: 'IS_EQUAL', value: 'Yes' }] }] }
        ]);
        expect(results.map((r) => r.ok)).toEqual([true, true, false, false, false, true]);
        expect(results[2].message).toMatch(/^Unknown reference '\$ref:b-missing'/);
        expect(results[4].message).toBe("'$ref:gone' names what operation #3 would have created, but that operation failed.");
        expect(doc.fields[0].properties!.jumps![0]).toMatchObject({ target: 'new-4', conditions: [{ fieldId: 'new-3' }] });
        expect(
            refDependencies([
                { op: 'add_page', ref: 'x' },
                { op: 'remove_page', pageId: '$ref:x' }
            ] as FormOp[]).map((s) => [...s])
        ).toEqual([[], [0]]);
        expect(
            run([
                { op: 'add_page', ref: 'x' },
                { op: 'add_page', ref: 'x' }
            ]).results[1].message
        ).toBe("The ref 'x' is already defined by operation #0; each ref names one new item.");
    });

    it('is all or nothing when atomic', () => {
        const before = smallForm();
        const out = run(
            [
                { op: 'update_form_info', title: 'New' },
                { op: 'remove_field', fieldId: 'nope' },
                { op: 'remove_page', pageId: 'nope' }
            ],
            before,
            true
        );
        expect(out.doc).toBe(before);
        expect(out.results.map((r) => r.ok)).toEqual([true, false, false]);
        expect(applied(out.results, true)).toBe(false);
        expect(applied(out.results, false)).toBe(true);
    });

    it('stops at the size limit', () => {
        const doc = smallForm();
        const ops = Array.from({ length: MAX_PAGES }, () => ({ op: 'add_page' }));
        const { results } = run(ops, doc);
        expect(results.filter((r) => r.ok)).toHaveLength(MAX_PAGES - 3);
        expect(results[MAX_PAGES - 3].message).toBe(`A form can have at most ${MAX_PAGES} pages; this would make ${MAX_PAGES + 1}.`);
        expect(results[MAX_PAGES - 2].message).toBe("Not applied: an earlier operation reached the form's size limit.");
        expect(tooManyOps(201)).toMatch(/^At most 200 operations/);
    });

    it('keeps the references of everything an op did not change', () => {
        const before = smallForm();
        const { doc } = run([{ op: 'update_field', fieldId: 'bio', patch: { title: 'x' } }], before);
        expect(doc.fields[0]).toBe(before.fields[0]);
        expect(doc.fields[2]).toBe(before.fields[2]);
        expect(doc.fields[1].properties!.fields![0]).toBe(before.fields[1].properties!.fields![0]);
        expect(doc.theme).toBe(before.theme);
    });

    it('reports unknown ops', () => {
        expect(one({ op: 'explode' }).result.message).toBe("Unknown operation 'explode'.");
    });
});
