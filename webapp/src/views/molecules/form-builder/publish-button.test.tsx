import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { PublishProblem, splitPublishProblems } from '@app/utils/publish-checks';

import { PublishProblemsDialog } from './publish-button';

const reason: PublishProblem = { code: 'missing_why_we_ask', fieldId: 'e', message: '"Email" asks for personal details.' };
const deadEnd: PublishProblem = { code: 'required_unanswerable', fieldId: 's', message: '"Intro" is required, but it only shows content.' };

function renderDialog(problems: PublishProblem[], publishChecksVersion?: number | null) {
    const { blocking, recommended } = splitPublishProblems(problems, publishChecksVersion);
    const onPublishAnyway = vi.fn();
    render(<PublishProblemsDialog blocking={blocking} recommended={recommended} onClose={vi.fn()} onPublishAnyway={onPublishAnyway} onShowQuestion={vi.fn()} canShowQuestion={() => true} />);
    return { onPublishAnyway };
}

describe('splitPublishProblems', () => {
    it('requires the reason only of forms created under the checks', () => {
        expect(splitPublishProblems([reason, deadEnd], 1)).toEqual({ blocking: [reason, deadEnd], recommended: [] });
        expect(splitPublishProblems([reason, deadEnd], undefined)).toEqual({ blocking: [deadEnd], recommended: [reason] });
        expect(splitPublishProblems([reason], null)).toEqual({ blocking: [], recommended: [reason] });
    });
});

describe('"Before you publish" dialog', () => {
    it('blocks a new form without a reason: no way to publish from the dialog', () => {
        renderDialog([reason], 1);
        expect(screen.getByRole('dialog', { name: 'Before you publish' })).toBeInTheDocument();
        expect(screen.getByText(/One thing would mislead or stop/)).toBeInTheDocument();
        expect(screen.getByTestId('publish-problems')).toHaveTextContent('"Email" asks for personal details.');
        expect(screen.queryByRole('button', { name: 'Publish anyway' })).not.toBeInTheDocument();
    });

    it('only recommends the reason on an older form, and lets it publish', () => {
        const { onPublishAnyway } = renderDialog([reason], undefined);
        expect(screen.getByText(/Recommended: people trust a form more/)).toBeInTheDocument();
        expect(screen.getByTestId('publish-recommendations')).toHaveTextContent('"Email" asks for personal details.');
        expect(screen.queryByTestId('publish-problems')).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Publish anyway' }));
        expect(onPublishAnyway).toHaveBeenCalledTimes(1);
    });

    it('still blocks a dead end on an older form, listing the reason as a recommendation', () => {
        renderDialog([reason, deadEnd], undefined);
        expect(screen.getByTestId('publish-problems')).toHaveTextContent('"Intro" is required');
        expect(screen.getByText('Also recommended')).toBeInTheDocument();
        expect(screen.getByTestId('publish-recommendations')).toHaveTextContent('"Email"');
        expect(screen.queryByRole('button', { name: 'Publish anyway' })).not.toBeInTheDocument();
    });

    it('sits on an opaque surface above the backdrop, so its text stays readable', () => {
        renderDialog([reason], undefined);
        const dialog = screen.getByRole('dialog', { name: 'Before you publish' });
        expect(dialog.className.split(' ')).toContain('bg-white');
        expect(dialog.className.split(' ')).toContain('z-modal');
    });
});
