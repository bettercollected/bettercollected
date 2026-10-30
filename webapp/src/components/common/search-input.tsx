import { useEffect, useMemo, useRef } from 'react';

import { useTranslation } from 'react-i18next';

import { debounce } from 'lodash';

import { SearchIcon } from '@app/components/icons/search';
import { placeHolder } from '@app/constants/locales/placeholder';
import { AppInput } from '@app/shadcn/components/ui/input';
import { cn } from '@app/shadcn/util/lib';

interface ISearchInputProps {
    handleSearch: (event: any) => void;
    className?: string;
    placeholder?: string;
    /** Accessible name; defaults to the placeholder (a placeholder alone is not a label). */
    ariaLabel?: string;
}

export default function SearchInput({ handleSearch, className, placeholder, ariaLabel }: ISearchInputProps) {
    const { t } = useTranslation();
    // The debounce is created once and calls the latest handler: callers pass a
    // fresh function on every render, and a re-render inside the 500 ms window
    // must neither drop the pending search nor restart the timer.
    const latestHandler = useRef(handleSearch);
    latestHandler.current = handleSearch;
    const debouncedResults = useMemo(() => debounce((event: any) => latestHandler.current(event), 500), []);
    // a search typed just before leaving the page must not fire afterwards
    useEffect(() => () => debouncedResults.cancel(), [debouncedResults]);

    const placeholderText = placeholder ? placeholder : t(placeHolder.search);
    return (
        <AppInput
            id='search-input'
            aria-label={ariaLabel ?? placeholderText}
            name="search-input"
            placeholder={placeholderText}
            onChange={debouncedResults}
            className={cn('w-full bg-white h-[40px] rounded', className)}
            icon={<SearchIcon />}
        />
    );
}
