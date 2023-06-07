import { useEffect, useMemo } from 'react';

import { useTranslation } from 'next-i18next';

import { debounce } from 'lodash';

import { InputAdornment } from '@mui/material';
import TextField from '@mui/material/TextField';

import { StyledTextField } from '@app/components/dashboard/workspace-forms-tab-content';
import { SearchIcon } from '@app/components/icons/search';
import { placeHolder } from '@app/constants/locales/placeholder';

interface ISearchInputProps {
    handleSearch: (event: any, value?: any) => void;
}

export default function SearchInput({ handleSearch }: ISearchInputProps) {
    const { t } = useTranslation();
    const debouncedResults = useMemo(() => {
        return debounce(handleSearch, 500);
    }, []);

    return (
        <StyledTextField>
            <TextField
                sx={{ height: '46px', padding: 0 }}
                size="small"
                name="search-input"
                placeholder={t(placeHolder.search)}
                onChange={debouncedResults}
                className={'w-full bg-white focus:bg-white active:bg-white'}
                InputProps={{
                    sx: {
                        paddingLeft: '16px'
                    },
                    endAdornment: (
                        <InputAdornment sx={{ padding: 0 }} position="end">
                            <SearchIcon />
                        </InputAdornment>
                    )
                }}
            />
        </StyledTextField>
    );
}
