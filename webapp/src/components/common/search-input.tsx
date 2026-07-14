import { useMemo } from 'react';

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
}

export default function SearchInput({ handleSearch, className, placeholder }: ISearchInputProps) {
    const { t } = useTranslation();
    const debouncedResults = useMemo(() => {
        return debounce(handleSearch, 500);
    }, [handleSearch]);

    return (
        <AppInput
            id='search-input'
            name="search-input"
            placeholder={placeholder ? placeholder : t(placeHolder.search)}
            onChange={debouncedResults}
            className={cn('w-full bg-white h-[40px] rounded-lg shadow-sm', className)}
            icon={<SearchIcon />}
        />
    );
}
