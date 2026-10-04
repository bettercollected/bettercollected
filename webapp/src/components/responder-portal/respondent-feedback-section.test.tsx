import React from 'react';

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import RespondentFeedbackSection from './respondent-feedback-section';

describe("RespondentFeedbackSection (the respondent's view)", () => {
    it('renders nothing without feedback', () => {
        const { container } = render(<RespondentFeedbackSection feedback={null} />);
        expect(container.innerHTML).toBe('');
    });

    it('shows the organisation, the current status and every update, newest first', () => {
        render(
            <RespondentFeedbackSection
                feedback={{
                    author: 'Acme Hiring',
                    currentStatus: 'Selected',
                    entries: [
                        { status: 'Under review', message: 'Thanks, we are looking at it', createdAt: '2026-10-01T10:00:00Z' },
                        { status: 'Selected', message: null, createdAt: '2026-10-02T10:00:00Z' },
                        { status: null, message: 'Please bring your passport', createdAt: '2026-10-03T10:00:00Z' }
                    ]
                }}
            />
        );
        expect(screen.getByText('Response from Acme Hiring')).toBeDefined();
        const items = screen.getAllByRole('listitem');
        expect(items).toHaveLength(3);
        expect(items[0].textContent).toContain('Please bring your passport');
        expect(items[2].textContent).toContain('Under review');
        // the current status badge plus the one in its update
        expect(screen.getAllByText('Selected')).toHaveLength(2);
    });

    it('falls back to the workspace title and says when there is nothing yet', () => {
        render(<RespondentFeedbackSection feedback={{ entries: [] }} workspaceTitle="Acme" />);
        expect(screen.getByText('Response from Acme')).toBeDefined();
        expect(screen.getByText(/No updates yet/)).toBeDefined();
    });
});
