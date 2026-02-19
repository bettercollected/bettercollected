import React, { useMemo } from 'react';

import { useTranslation } from 'next-i18next';

import { debounce } from 'lodash';

import AppTextField from '@Components/Common/Input/AppTextField';
import { SearchIcon } from '@app/Components/icons/search';
import { placeHolder } from '@app/constants/locales/placeholder';
import { cn } from '@app/shadcn/util/lib';

interface ISearchInputProps {
    handleSearch: (event: any) => void;
    className?: string;
    placeholder?: string;
}

export default function SearchInput({ handleSearch, className, placeholder }: ISearchInputProps) {
    const { t } = useTranslation();
    const debouncedResults = useMemo(() => {
        return debounce(handleSearch, 500);
    }, []);

    return (
        <AppTextField
            name="search-input"
            placeholder={placeholder ? placeholder : t(placeHolder.search)}
            onChange={debouncedResults}
            className={cn('w-full bg-white h-[40px] rounded-lg shadow-sm', className)}
            showIcon={true}
            icon={<SearchIcon />}
            iconPosition="start"
        />
    );
}
