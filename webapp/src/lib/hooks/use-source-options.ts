'use client';

import { useCallback, useContext, useEffect, useRef, useState } from 'react';

import { fetchSourceOptions } from '@app/lib/source-options';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { selectResponderForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { usePreviewOptionSourceMutation } from '@app/store/option-lists/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { SourceOption, SourceOptionsPage } from '@app/utils/option-sources';
import { PreviewModeContext } from '@app/views/molecules/responder-form-fields/preview-mode-context';

const PAGE = 50;
const DEBOUNCE_MS = 250;

export interface SourceOptionsState {
    items: SourceOption[];
    total: number;
    truncated: boolean;
    available: boolean;
    loading: boolean;
    failed: boolean;
    canLoadMore: boolean;
    loadMore: () => void;
}

/**
 * The choices of a question whose options come from a source, a page at a time, for a search text and the ids
 * chosen in the question a dependent list follows. A respondent's page asks the public options route; the builder's
 * preview (a creator looking at the form) asks the authenticated preview route with the source the form holds.
 * An older request is dropped when a newer one starts. Nothing is cached beyond the component: another form's
 * answers must not outlive the page, and the server serves them fresh.
 */
export function useSourceOptions(field: StandardFormFieldDto, { query, parentIds, parentLabels, enabled }: { query: string; parentIds: string[]; parentLabels: string[]; enabled: boolean }): SourceOptionsState {
    const workspace = useAppSelector(selectWorkspace);
    const responderForm = useAppSelector(selectResponderForm);
    const preview = useContext(PreviewModeContext);
    const [previewSource] = usePreviewOptionSourceMutation();
    const [page, setPage] = useState<SourceOptionsPage>({ items: [], total: 0, truncated: false, available: true });
    const [loading, setLoading] = useState(false);
    const [failed, setFailed] = useState(false);
    const [debounced, setDebounced] = useState(query);
    const request = useRef(0);
    const source = field.properties?.optionSource;
    const parentKey = parentIds.join('\u0000');
    const labelKey = parentLabels.join('\u0000');

    useEffect(() => {
        const timer = setTimeout(() => setDebounced(query), DEBOUNCE_MS);
        return () => clearTimeout(timer);
    }, [query]);

    const fetchPage = useCallback(
        async (offset: number): Promise<SourceOptionsPage> => {
            if (preview) {
                const result: any = await previewSource({ workspaceId: workspace?.id, source: source!, parentLabels, q: debounced || undefined, limit: PAGE, offset });
                if (!result?.data) throw new Error('preview unavailable');
                return { items: result.data.items, total: result.data.total, truncated: !!result.data.truncated, available: result.data.available !== false };
            }
            return fetchSourceOptions({ workspaceId: workspace?.id, formId: responderForm?.formId as string, fieldId: field.id, q: debounced, offset, limit: PAGE, parent: parentIds });
        },
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [preview, workspace?.id, responderForm?.formId, field.id, debounced, parentKey, labelKey, source?.kind]
    );

    useEffect(() => {
        if (!enabled || !source) return;
        const mine = ++request.current;
        setLoading(true);
        setFailed(false);
        fetchPage(0)
            .then((result) => {
                if (mine !== request.current) return;
                setPage(result);
                setLoading(false);
            })
            .catch(() => {
                if (mine !== request.current) return;
                setFailed(true);
                setLoading(false);
            });
        return () => {
            request.current++;
        };
    }, [enabled, fetchPage, source]);

    const loadMore = useCallback(() => {
        const mine = ++request.current;
        setLoading(true);
        fetchPage(page.items.length)
            .then((result) => {
                if (mine !== request.current) return;
                setPage((previous) => ({ ...result, items: [...previous.items, ...result.items.filter((item) => !previous.items.some((known) => known.id === item.id))] }));
                setLoading(false);
            })
            .catch(() => {
                if (mine !== request.current) return;
                setFailed(true);
                setLoading(false);
            });
    }, [fetchPage, page.items.length]);

    return { ...page, loading, failed, canLoadMore: page.items.length < page.total, loadMore };
}
