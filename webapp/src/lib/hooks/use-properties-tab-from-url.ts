import { useEffect } from 'react';

import { useSearchParams } from 'next/navigation';

import { propertiesTabFromParam, usePropertiesTab } from '@app/store/jotai/properties-tab';

/**
 * Opens the properties drawer on the tab a link names: `/edit?tab=form` lands on
 * the Form tab (purpose, retention, privacy link), as Settings' "Open in the
 * builder" does. Applied when the page opens or the value changes; anything
 * else leaves the drawer as it is.
 */
export function usePropertiesTabFromUrl() {
    const searchParams = useSearchParams();
    const { setPropertiesTab } = usePropertiesTab();
    const requested = propertiesTabFromParam(searchParams?.get('tab'));
    useEffect(() => {
        if (requested) setPropertiesTab(requested);
    }, [requested, setPropertiesTab]);
}
