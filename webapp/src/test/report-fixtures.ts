import type { ReportCardDef, ReportCardResult, ReportCatalogue, ReportDefinition, ReportGroup, ReportResult } from '@app/utils/report';

/**
 * A made-up form and its figures for the report tests: a staff survey with
 * neutral questions and invented numbers. `figures` answers a definition the way
 * the API does (same shapes), from fixed counts, so a test can rely on them.
 */
export const TOTAL = 212;

const EMPTY = ['is_empty', 'is_not_empty'];
const NUMBER = ['=', '!=', '>', '>=', '<', '<=', 'between'];

export const catalogue: ReportCatalogue = {
    fields: [
        {
            key: 'q:team', filterOps: ['is', 'is_not', 'any_of', ...EMPTY],
            label: 'Which team are you in?',
            kind: 'choice',
            dimension: true,
            measures: ['count'],
            versions: [1, 2],
            inCurrentVersion: true,
            options: [
                { id: 'north', label: 'North' },
                { id: 'south', label: 'South' },
                { id: 'east', label: 'East' },
                { id: 'west', label: 'West' }
            ]
        },
        {
            key: 'q:tools', filterOps: ['has_any', 'has_all', ...EMPTY],
            label: 'Which tools do you use?',
            kind: 'choices',
            dimension: true,
            measures: ['count'],
            versions: [1, 2],
            inCurrentVersion: true,
            options: [
                { id: 'mail', label: 'Mail' },
                { id: 'chat', label: 'Chat' },
                { id: 'wiki', label: 'Wiki' },
                { id: 'cal', label: 'Calendar' },
                { id: 'trk', label: 'Tracker' }
            ]
        },
        { key: 'q:score', filterOps: [...NUMBER, ...EMPTY], label: 'How satisfied are you?', kind: 'scale', dimension: true, measures: ['count', 'avg', 'min', 'max'], versions: [1, 2], inCurrentVersion: true },
        { key: 'q:years', filterOps: [...NUMBER, ...EMPTY], label: 'Years at the organisation', kind: 'number', dimension: false, measures: ['count', 'avg', 'sum', 'min', 'max'], versions: [1, 2], inCurrentVersion: true },
        { key: 'q:remote', filterOps: ['is', ...EMPTY], label: 'Do you work remotely?', kind: 'yes_no', dimension: true, measures: ['count'], versions: [1, 2], inCurrentVersion: true }
    ],
    builtins: [
        { key: 'submitted_at', buckets: ['day', 'week', 'month', 'year'] },
        { key: 'form_version' },
        { key: 'respondent', groups: [{ key: 'anonymous', label: 'Anonymous' }, { key: 'known', label: 'Identified' }] },
        { key: 'ending', groups: [{ key: 'thanks', label: 'Thank you' }] },
        { key: 'status', measures: ['count'], groups: [{ key: 'none', label: 'None' }, { key: 'pending', label: 'Pending' }, { key: 'declined', label: 'Declined' }, { key: 'success', label: 'Success' }] },
        { key: 'feedback_status', measures: ['count'] },
        { key: 'source', groups: [{ key: 'form', label: 'Form' }, { key: 'api', label: 'API' }, { key: 'csv', label: 'CSV import' }] }
    ],
    limits: { maxRows: 20000, maxCards: 24, maxMeasures: 5 }
};

const group = (key: string, label: string, n: number, values: Array<number | null> = [n]): ReportGroup => ({ key, label, n, values, valueN: values.map(() => n) });

const COUNTS: Record<string, Array<[string, string, number]>> = {
    'q:team': [['north', 'North', 74], ['south', 'South', 52], ['east', 'East', 41], ['west', 'West', 31], ['other', 'Other', 0], ['removed', 'Removed option', 0]],
    'q:tools': [['mail', 'Mail', 180], ['chat', 'Chat', 151], ['wiki', 'Wiki', 66], ['cal', 'Calendar', 120], ['trk', 'Tracker', 38]],
    'q:score': [['1', '1', 6], ['2', '2', 14], ['3', '3', 41], ['4', '4', 82], ['5', '5', 55]],
    'q:remote': [['yes', 'Yes', 96], ['no', 'No', 102]],
    respondent: [['anonymous', 'Anonymous', 140], ['known', 'Identified', 72]],
    source: [['form', 'Form', 200], ['api', 'API', 12], ['csv', 'CSV import', 0]],
    form_version: [['1', '1', 60], ['2', '2', 152]]
};

function days(count: number): Array<[string, string, number]> {
    return Array.from({ length: count }, (_, index) => {
        const day = `2026-10-${String(index + 1).padStart(2, '0')}`;
        return [day, day, 4 + ((index * 7) % 9)] as [string, string, number];
    });
}

/** The figures of one card. */
export function cardFigures(card: ReportCardDef, n = TOTAL): ReportCardResult {
    const dimension = card.dimension?.field;
    const first = card.measures[0];
    if (!dimension) {
        const value = first.agg === 'count' ? n : first.agg === 'avg' ? 7.4 : first.agg === 'sum' ? 1569 : first.agg === 'min' ? 0 : 31;
        return { id: card.id, n, answered: first.agg === 'count' ? n : 198, skipped: first.agg === 'count' ? 0 : n - 198, multiple: false, groups: [group('all', '', n, card.measures.map(() => value))], otherGroups: { n: 0, count: 0 }, truncated: false };
    }
    const rows = dimension === 'submitted_at' ? days(card.dimension?.bucket === 'month' ? 6 : 30) : (COUNTS[dimension] ?? [['a', 'A', 1]]);
    const groups = rows.map(([key, label, count]) => group(key, label, count, card.measures.map((measure) => (measure.agg === 'count' ? count : measure.agg === 'avg' ? 4.2 : count))));
    const answered = dimension === 'q:tools' ? 198 : groups.reduce((sum, g) => sum + g.n, 0);
    return { id: card.id, n, answered, skipped: n - answered, multiple: dimension === 'q:tools', groups, otherGroups: { n: 0, count: 0 }, truncated: false };
}

export function figures(definition: ReportDefinition, n = TOTAL, notices: string[] = []): ReportResult {
    return { definitionHash: 'h', token: 't', generatedAt: '2026-11-12T10:00:00Z', n, scanned: n, cards: definition.cards.map((card) => cardFigures(card, n)), notices };
}
