import { existsSync, readFileSync } from 'fs';
import { resolve } from 'path';

import i18n from 'i18next';
import { describe, expect, it } from 'vitest';

import { AuditEntryDto, AuditLabels } from '@app/models/dtos/audit-log-dto';
import '@app/shared/hocs/i18n-provider';

import { AUDIT_EVENTS, describeEntry } from './sentences';

const LABELS: AuditLabels = {
    members: {
        u_sanne: { status: 'member', name: 'Sanne de Vries' },
        u_pim: { status: 'member', name: 'Pim Jansen' },
        u_left: { status: 'former' },
        u_blank: { status: 'member' }
    },
    forms: { f_join: { status: 'available', title: 'Join the volunteers' }, f_gone: { status: 'gone' } },
    teams: { g_intake: { status: 'available', name: 'Intake' }, g_gone: { status: 'gone' } }
};

const ids = ['u_sanne', 'u_pim', 'u_left', 'u_blank', 'f_join', 'f_gone', 'g_intake', 'g_gone', 'r_1', 'k_9'];

// one entry per kind, with the fields that kind carries
const SAMPLES: Record<(typeof AUDIT_EVENTS)[number], Partial<AuditEntryDto>> = {
    access_grant_added: { actorId: 'u_sanne', groupId: 'g_intake', formId: 'f_join', grantRole: 'REVIEWER', grantExport: false },
    access_grant_changed: { actorId: 'u_sanne', targetUserId: 'u_pim', formId: 'f_join', grantRole: 'VIEWER' },
    access_grant_removed: { actorId: 'u_sanne', targetUserId: 'u_pim', formId: 'f_join' },
    access_mode_changed: { actorId: 'u_sanne', formId: 'f_join', accessMode: 'restricted' },
    team_created: { actorId: 'u_sanne', groupId: 'g_intake' },
    team_renamed: { actorId: 'u_sanne', groupId: 'g_intake' },
    team_deleted: { actorId: 'u_sanne', groupId: 'g_gone', count: 3 },
    team_member_added: { actorId: 'u_sanne', targetUserId: 'u_pim', groupId: 'g_intake' },
    team_member_removed: { actorId: 'u_sanne', targetUserId: 'u_pim', groupId: 'g_intake' },
    team_linked: { actorId: 'u_sanne', groupId: 'g_intake' },
    access_member_purged: { actorId: 'u_sanne', targetUserId: 'u_left', count: 4 },
    member_invited: { actorId: 'u_sanne', role: 'REVIEWER' },
    member_invitation_revoked: { actorId: 'u_sanne' },
    member_invitation_accepted: { actorId: 'u_pim', targetUserId: 'u_pim', role: 'COLLABORATOR' },
    member_removed: { actorId: 'u_sanne', targetUserId: 'u_left' },
    member_role_changed: { actorId: 'u_sanne', targetUserId: 'u_pim', role: 'ADMIN', previousRole: 'VIEWER' },
    form_published: { actorId: 'u_sanne', formId: 'f_join' },
    form_deleted: { actorId: 'u_sanne', formId: 'f_gone' },
    form_creator_reassigned: { actorId: 'u_sanne', targetUserId: 'u_left', toUserId: 'u_pim', formId: 'f_join' },
    response_staff_edit: { actorId: 'u_pim', formId: 'f_join', responseId: 'r_1', revision: 2 },
    response_revision_read: { actorId: 'u_pim', formId: 'f_join', responseId: 'r_1', revision: 1 },
    responses_deleted: { actorId: 'u_sanne', formId: 'f_join', count: 12 },
    response_export: { actorId: 'u_sanne', formId: 'f_join', exportChannel: 'export', exportFormat: 'csv', count: 40 },
    api_key_revoked: { actorId: 'u_sanne', targetUserId: 'u_left', keyId: 'k_9', reason: 'member_removed' },
    api_key_created: { actorId: 'u_sanne', keyId: 'k_9', keyRole: 'VIEWER', formScope: 'listed' },
    api_key_role_changed: { actorId: 'u_sanne', keyId: 'k_9', keyRole: 'EDITOR', keyRoleBefore: 'VIEWER', widened: true },
    api_key_scope_changed: { actorId: 'u_sanne', keyId: 'k_9', formScope: 'listed' },
    api_key_form_added: { actorId: 'u_sanne', keyId: 'k_9', formId: 'f_join' },
    api_key_form_removed: { actorId: 'u_sanne', keyId: 'k_9', formId: 'f_join' },
    sso_break_glass_request: { actorId: 'u_sanne', method: 'GET', path: '/workspaces/{workspace_id}/forms' },
    sso_break_glass_sign_in: { actorId: 'u_sanne' },
    totp_policy_changed: { actorId: 'u_sanne', required: true },
    totp_reset: { actorId: 'u_sanne', targetUserId: 'u_pim' },
    sso_connection_created: { actorId: 'u_sanne', connectionType: 'saml' },
    sso_connection_enabled: { actorId: 'u_sanne', connectionType: 'oidc' },
    sso_connection_disabled: { actorId: 'u_sanne' },
    sso_connection_deleted: { actorId: 'u_sanne' },
    sso_required_changed: { actorId: 'u_sanne', required: true },
    sso_default_role_changed: { actorId: 'u_sanne', role: 'VIEWER', previousRole: 'EDITOR' },
    domain_claimed: { actorId: 'u_sanne' },
    domain_verified: { actorId: 'u_sanne' },
    domain_removed: { actorId: 'u_sanne' },
    scim_token_created: { actorId: 'u_sanne', directoryType: 'generic' },
    scim_token_rotated: { actorId: 'u_sanne' },
    scim_token_revoked: { actorId: 'u_sanne' },
    scim_group_role_changed: { actorId: 'u_sanne', role: 'REVIEWER', previousRole: 'VIEWER' },
    ai_consent_changed: { actorId: 'u_sanne', enabled: true, provider: 'openai' },
    custom_domain_changed: { actorId: 'u_sanne' },
    custom_domain_removed: { actorId: 'u_sanne' },
    email_action_created: { actorId: 'u_sanne', formId: 'f_join' },
    email_action_updated: { actorId: 'u_sanne', formId: 'f_join', changed: ['team_recipients', 'respondent_copy'] },
    email_action_enabled: { actorId: 'u_sanne', formId: 'f_join' },
    email_action_disabled: { actorId: 'u_sanne', formId: 'f_join' },
    email_action_deleted: { actorId: 'u_sanne', formId: 'f_join' },
    registration_service_created: { actorId: 'u_sanne' },
    registration_service_updated: { actorId: 'u_sanne', changed: ['base_url', 'secret'] },
    registration_service_deleted: { actorId: 'u_sanne' },
    form_registration_enabled: { actorId: 'u_sanne', formId: 'f_join' },
    form_registration_changed: { actorId: 'u_sanne', formId: 'f_join', changed: ['path'] },
    form_registration_disabled: { actorId: 'u_sanne', formId: 'f_join' },
    form_copied_out: { actorId: 'u_sanne', formId: 'f_join' },
    form_promoted: { actorId: 'u_sanne', formId: 'f_join', count: 3 },
    audit_log_exported: { actorId: 'u_sanne', exportFormat: 'csv', count: 120 }
};

const entry = (event: string, extra: Partial<AuditEntryDto> = {}): AuditEntryDto => ({ id: 'e1', event, at: '2026-11-01T12:00:00Z', ...extra });
const say = (lng: 'en' | 'nl', e: AuditEntryDto, formId?: string) => describeEntry(e, { labels: LABELS, t: i18n.getFixedT(lng) as any, formId });

describe('the sentence table', () => {
    it('lists every kind the server can return (backend services/audit_log/catalog.py)', () => {
        const catalog = resolve(__dirname, '../../../../backend/backend/app/services/audit_log/catalog.py');
        // the catalogue is part of this repository: a missing file is a failure, not a reason to skip the check
        expect(existsSync(catalog), `${catalog} is missing`).toBe(true);
        const schema = readFileSync(resolve(__dirname, '../../../../backend/backend/app/schemas/workspace_audit_event.py'), 'utf8');
        const source = readFileSync(catalog, 'utf8');
        const constants = Object.fromEntries([...schema.matchAll(/^([A-Z_]+) = "([a-z_]+)"$/gm)].map((m) => [m[1], m[2]]));
        const body = source.slice(source.indexOf('AREAS:'), source.indexOf('ACCOUNT_LEVEL:'));
        const listed = new Set<string>();
        // a tuple constant of the schema (API_KEY_EVENTS, SETTINGS_EVENTS, AUTOMATION_EVENTS) is the kinds it names
        const tuple = (name: string) => [...(schema.match(new RegExp(`^${name} = \\(([^)]*)\\)`, 'm'))?.[1] ?? '').matchAll(/([A-Z_]+),/g)].map((m) => m[1]);
        for (const m of body.matchAll(/E\.([A-Z_]+)/g)) {
            if (constants[m[1]]) listed.add(constants[m[1]]);
            else for (const name of tuple(m[1])) listed.add(constants[name]);
        }
        // every kind the server lists has a sentence (the page may know more than a server that has not got them yet)
        expect([...listed].filter((kind) => !(AUDIT_EVENTS as readonly string[]).includes(kind))).toEqual([]);
    });

    it('has a sample for every kind', () => {
        expect(Object.keys(SAMPLES).sort()).toEqual([...AUDIT_EVENTS].sort());
    });

    for (const lng of ['en', 'nl'] as const) {
        describe(lng, () => {
            for (const event of AUDIT_EVENTS) {
                it(`${event} reads as a plain sentence, with no id of a person, form or response and no raw key`, () => {
                    const sentence = say(lng, entry(event, SAMPLES[event]));
                    expect(sentence.key).not.toBe('AUDIT_LOG.SENTENCE.FALLBACK');
                    expect(sentence.text).toMatch(/\.$/);
                    expect(sentence.text).not.toMatch(/\{\{|AUDIT_LOG|WORKSPACE_ROLES|undefined|null|[\uE000\uE001]/);
                    for (const id of ids) expect(sentence.text).not.toContain(id);
                    // a sentence starts with a capital
                    expect(sentence.text[0]).toBe(sentence.text[0].toLocaleUpperCase());
                });
            }
        });
    }

    it('words a grant in English, with the role, the form and the export flag', () => {
        expect(say('en', entry('access_grant_added', { actorId: 'u_sanne', groupId: 'g_intake', formId: 'f_join', grantRole: 'REVIEWER' })).text).toBe('Sanne de Vries gave the team Intake Reviewer access to Join the volunteers.');
        expect(say('en', entry('access_grant_added', { actorId: 'u_sanne', targetUserId: 'u_pim', formId: 'f_join', grantRole: 'REVIEWER', grantExport: true })).text).toBe(
            'Sanne de Vries gave Pim Jansen Reviewer access to Join the volunteers, including export of responses.'
        );
    });

    it('words the same grant in Dutch', () => {
        expect(say('nl', entry('access_grant_added', { actorId: 'u_sanne', groupId: 'g_intake', formId: 'f_join', grantRole: 'REVIEWER' })).text).toBe('Sanne de Vries gaf het team Intake toegang als Beoordelaar tot Join the volunteers.');
    });

    it('sets the names in bold and nothing else', () => {
        const { segments } = say('en', entry('team_member_added', SAMPLES.team_member_added));
        expect(segments.filter((s) => s.strong).map((s) => s.text)).toEqual(['Sanne de Vries', 'Pim Jansen', 'Intake']);
        expect(segments.filter((s) => !s.strong).map((s) => s.text).join('')).toBe(' added  to the team .');
    });

    it('says "a member who has left" for a former member and "an item that no longer exists" for a gone form or team', () => {
        expect(say('en', entry('member_removed', { actorId: 'u_sanne', targetUserId: 'u_left' })).text).toBe('Sanne de Vries removed a member who has left from the workspace.');
        expect(say('nl', entry('member_removed', { actorId: 'u_sanne', targetUserId: 'u_left' })).text).toBe('Sanne de Vries verwijderde een lid dat is vertrokken uit de werkruimte.');
        expect(say('en', entry('form_deleted', { actorId: 'u_sanne', formId: 'f_gone' })).text).toBe('Sanne de Vries deleted an item that no longer exists.');
        expect(say('en', entry('team_member_added', { actorId: 'u_sanne', targetUserId: 'u_pim', groupId: 'g_gone' })).text).toBe('Sanne de Vries added Pim Jansen to the team an item that no longer exists.');
    });

    it('treats an id the page has no label for like a gone one, never printing it', () => {
        const sentence = say('en', entry('form_published', { actorId: 'u_unknown', formId: 'f_unlabelled' }));
        expect(sentence.text).toBe('A member who has left published an item that no longer exists.');
        expect(sentence.text).not.toContain('unknown');
        expect(sentence.text).not.toContain('unlabelled');
    });

    it('says "someone" when no actor was recorded and "a member" when a name could not be looked up', () => {
        expect(say('en', entry('form_published', { formId: 'f_join' })).text).toBe('Someone published Join the volunteers.');
        expect(say('en', entry('form_published', { actorId: 'u_blank', formId: 'f_join' })).text).toBe('A member published Join the volunteers.');
    });

    it('says "this form" on a form\'s own page', () => {
        expect(say('en', entry('access_mode_changed', SAMPLES.access_mode_changed), 'f_join').text).toBe('Sanne de Vries made this form restricted: only people with access can open it.');
        expect(say('nl', entry('access_mode_changed', { ...SAMPLES.access_mode_changed, accessMode: 'workspace' }), 'f_join').text).toBe('Sanne de Vries opende dit formulier voor iedereen in de werkruimte die formulieren mag lezen.');
    });

    it('pluralises counts', () => {
        expect(say('en', entry('team_deleted', { actorId: 'u_sanne', count: 1 })).text).toBe('Sanne de Vries deleted a team (1 grant removed).');
        expect(say('en', entry('team_deleted', { actorId: 'u_sanne', count: 3 })).text).toBe('Sanne de Vries deleted a team (3 grants removed).');
        expect(say('en', entry('responses_deleted', { actorId: 'u_sanne', formId: 'f_join', count: 1 })).text).toBe('Sanne de Vries deleted 1 response of Join the volunteers.');
        expect(say('nl', entry('responses_deleted', { actorId: 'u_sanne', formId: 'f_join', count: 2 })).text).toBe('Sanne de Vries verwijderde 2 reacties van Join the volunteers.');
        // no count recorded: the sentence does not invent one
        expect(say('en', entry('team_deleted', { actorId: 'u_sanne' })).text).toBe('Sanne de Vries deleted a team.');
    });

    it('chooses the variant the fields call for', () => {
        expect(say('en', entry('totp_policy_changed', { actorId: 'u_sanne', required: false })).text).toBe('Sanne de Vries no longer requires an authenticator app.');
        expect(say('en', entry('member_role_changed', { actorId: 'u_sanne', targetUserId: 'u_pim', role: 'ADMIN' })).text).toBe('Sanne de Vries changed the role of Pim Jansen to Admin.');
        expect(say('en', entry('response_export', { actorId: 'u_sanne', formId: 'f_join', exportChannel: 'export', exportFormat: 'csv', count: 40 })).text).toBe('Sanne de Vries exported responses of Join the volunteers (CSV, 40 responses).');
        expect(say('en', entry('api_key_revoked', { actorId: 'u_sanne', targetUserId: 'u_left', reason: 'account_deleted' })).text).toBe('An API key was revoked because its creator, a member who has left, deleted their account.');
        expect(say('en', entry('response_staff_edit', { actorId: 'u_pim', formId: 'f_join', revision: 2 })).text).toBe('Pim Jansen edited answers of a response of Join the volunteers (change 2).');
        expect(say('en', entry('member_invitation_accepted', { actorId: 'u_pim', role: 'COLLABORATOR' })).text).toBe('Pim Jansen joined the workspace as Editor.');
    });

    it('words an API key that acts as its creator, and an admin or workspace revocation', () => {
        expect(say('en', entry('api_key_created', { actorId: 'u_sanne', keyRole: 'creator' })).text).toBe("Sanne de Vries created an API key that acts with its creator's access.");
        expect(say('en', entry('api_key_role_changed', { actorId: 'u_sanne', keyRole: 'EDITOR', keyRoleBefore: 'creator' })).text).toBe("Sanne de Vries changed the role of an API key from its creator's access to Editor.");
        expect(say('nl', entry('api_key_role_changed', { actorId: 'u_sanne', keyRole: 'creator', keyRoleBefore: 'VIEWER' })).text).toBe('Sanne de Vries wijzigde de rol van een API-sleutel van Kijker naar de toegang van de maker.');
        expect(say('en', entry('api_key_revoked', { actorId: 'u_sanne', reason: 'admin' })).text).toBe('Sanne de Vries revoked an API key.');
    });

    it('words the settings and integration kinds, with their facts', () => {
        expect(say('en', entry('sso_connection_created', { actorId: 'u_sanne', connectionType: 'saml' })).text).toBe('Sanne de Vries added a single sign-on connection (SAML).');
        expect(say('nl', entry('sso_required_changed', { actorId: 'u_sanne', required: false })).text).toBe('Sanne de Vries verplicht geen single sign-on meer.');
        expect(say('en', entry('sso_default_role_changed', { actorId: 'u_sanne', role: 'VIEWER', previousRole: 'EDITOR' })).text).toBe('Sanne de Vries changed the role people get when they sign in with single sign-on from Editor to Viewer.');
        expect(say('en', entry('scim_group_role_changed', { actorId: 'u_sanne', previousRole: 'VIEWER' })).text).toBe('Sanne de Vries stopped mapping a directory group to a role.');
        expect(say('en', entry('ai_consent_changed', { actorId: 'u_sanne', enabled: false, provider: 'openai' })).text).toBe('Sanne de Vries turned off AI features for the workspace.');
        expect(say('en', entry('email_action_updated', { actorId: 'u_sanne', formId: 'f_join', changed: ['team_recipients', 'respondent_copy', 'not_a_part'] })).text).toBe(
            'Sanne de Vries changed an email action of Join the volunteers (changed: team recipients, copy to the respondent).'
        );
        expect(say('nl', entry('form_registration_enabled', { actorId: 'u_sanne', formId: 'f_join' })).text).toBe('Sanne de Vries zette het doorsturen van de inzendingen van Join the volunteers naar een zaaksysteem aan.');
        expect(say('en', entry('registration_service_updated', { actorId: 'u_sanne', changed: ['secret'] })).text).toBe('Sanne de Vries changed a case-system service (changed: secret).');
        // the id of the AI provider and of a directory never reach the screen
        expect(say('en', entry('ai_consent_changed', { actorId: 'u_sanne', enabled: true, provider: 'openai' })).text).not.toMatch(/openai/i);
    });

    it('words an export of the log, with its format and size, and says which form for a form export', () => {
        expect(say('en', entry('audit_log_exported', { actorId: 'u_sanne', exportFormat: 'csv', count: 120 })).text).toBe('Sanne de Vries exported the activity log (CSV, 120 entries).');
        expect(say('en', entry('audit_log_exported', { actorId: 'u_sanne', exportFormat: 'json', count: 1, formId: 'f_join' })).text).toBe('Sanne de Vries exported the activity of Join the volunteers (JSON, 1 entry).');
        expect(say('nl', entry('audit_log_exported', { actorId: 'u_sanne', exportFormat: 'csv', count: 120 })).text).toBe('Sanne de Vries exporteerde de activiteit (CSV, 120 regels).');
        expect(say('nl', entry('audit_log_exported', { actorId: 'u_sanne' })).text).toBe('Sanne de Vries exporteerde de activiteit.');
    });

    it('words a form copied to or from another workspace, naming no workspace', () => {
        expect(say('en', entry('form_copied_out', { actorId: 'u_sanne', formId: 'f_join' })).text).toBe('Sanne de Vries copied Join the volunteers to another workspace.');
        expect(say('en', entry('form_promoted', { actorId: 'u_sanne', formId: 'f_join', count: 3 })).text).toBe('Sanne de Vries copied Join the volunteers in from another workspace (3 adjustments to fit).');
        expect(say('nl', entry('form_promoted', { actorId: 'u_sanne', formId: 'f_join', count: 1 })).text).toBe('Sanne de Vries kopieerde Join the volunteers vanuit een andere werkruimte hierheen (1 aanpassing om te passen).');
        expect(say('en', entry('form_promoted', { actorId: 'u_sanne', formId: 'f_join', count: 0 })).text).toBe('Sanne de Vries copied Join the volunteers in from another workspace.');
    });

    it('falls back to a neutral sentence for a kind it does not know, in both languages', () => {
        expect(say('en', entry('webhook_created', { actorId: 'u_sanne', formId: 'f_join' }))).toMatchObject({ text: 'An action was recorded.', key: 'AUDIT_LOG.SENTENCE.FALLBACK' });
        expect(say('nl', entry('something_new')).text).toBe('Er is een handeling vastgelegd.');
        // an unknown role of a known kind does not print the code
        expect(say('en', entry('member_invited', { actorId: 'u_sanne', role: 'SUPERUSER' })).text).toBe('Sanne de Vries invited someone to join the workspace as a role.');
    });

    it('cannot be made to forge a bold mark by a name', () => {
        const labels: AuditLabels = { ...LABELS, members: { u_evil: { status: 'member', name: 'Eve\uE000 Mallory\uE001' } } };
        const sentence = describeEntry(entry('form_published', { actorId: 'u_evil', formId: 'f_join' }), { labels: { ...labels, forms: LABELS.forms }, t: i18n.getFixedT('en') as any });
        expect(sentence.text).toBe('Eve Mallory published Join the volunteers.');
        expect(sentence.segments.filter((s) => s.strong).map((s) => s.text)).toEqual(['Eve Mallory', 'Join the volunteers']);
    });
});
