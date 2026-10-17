// Test data for the AI proposal change list (vitest only).
import { AIProposal } from './ai-proposal';

export const empty = () => ({ added: [], removed: [], moved: [], changed: [] });

export const BEFORE_FORM = {
    title: 'Visit',
    fields: [{ id: 'page-1', index: 0, type: 'slide', properties: { fields: [{ id: 'f1', index: 0, type: 'short_text', title: 'Your name' }] } }]
};

export const PROPOSAL: AIProposal = {
    id: '0123456789abcdef01234567-0011223344556677',
    summary: 'Here is what I would change.',
    ops: [{ op: 'add_page', ref: 'p2' }, { op: 'add_field' }, { op: 'update_theme' }, { op: 'set_section_title' }, { op: 'update_field' }, { op: 'remove_field' }],
    form: {
        title: 'Visit',
        theme: { title: 'Plain', primary: '#111111' },
        fields: [
            { id: 'page-1', index: 0, type: 'slide', properties: { sectionTitle: 'About you', fields: [{ id: 'f1', index: 0, type: 'short_text', title: 'Your name', validations: { required: true } }] } },
            { id: 'page-2', index: 1, type: 'slide', properties: { fields: [{ id: 'f-post', index: 0, type: 'short_text', title: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Postcode' }] }] } }] } }
        ]
    },
    diff: {
        form: [{ path: '/theme/title', before: 'Default', after: 'Plain' }],
        pages: { ...empty(), added: [{ id: 'page-2', path: '/pages/1' }] },
        fields: { ...empty(), added: [{ id: 'f-post', path: '/pages/1/fields/0' }] },
        changed: true
    },
    results: [
        { index: 0, op: 'add_page', ok: true, message: 'Added page 2' },
        { index: 1, op: 'add_field', ok: true, message: "Added 'Postcode'" },
        { index: 2, op: 'update_theme', ok: true, message: "Applied theme 'Plain'" },
        { index: 3, op: 'set_section_title', ok: true, message: 'Set the section title' },
        { index: 4, op: 'update_field', ok: true, message: "Updated 'Your name'" },
        { index: 5, op: 'remove_field', ok: false, message: "Field 'nope' was not found." }
    ],
    steps: [
        { index: 0, requires: [], diff: { form: [], pages: { ...empty(), added: [{ id: 'page-2', path: '/pages/1' }] }, fields: empty() } },
        { index: 1, requires: [0], diff: { form: [], pages: empty(), fields: { ...empty(), added: [{ id: 'f-post', path: '/pages/1/fields/0' }] } } },
        {
            index: 2,
            requires: [],
            diff: {
                form: [
                    { path: '/theme/title', before: 'Default', after: 'Plain' },
                    { path: '/theme/primary', before: '#000000', after: '#111111' }
                ],
                pages: empty(),
                fields: empty()
            }
        },
        { index: 3, requires: [], diff: { form: [], pages: { ...empty(), changed: [{ id: 'page-1', path: '/pages/0', changes: [{ path: '/pages/0/sectionTitle', before: null, after: 'About you' }] }] }, fields: empty() } },
        { index: 4, requires: [], diff: { form: [], pages: empty(), fields: { ...empty(), changed: [{ id: 'f1', path: '/pages/0/fields/0', changes: [{ path: '/pages/0/fields/0/validations/required', before: null, after: true }] }] } } }
    ]
};
