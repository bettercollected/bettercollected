import {useMemo} from 'react';

import {useTranslation} from 'next-i18next';

import {debounce} from 'lodash';

import {InputAdornment} from '@mui/material';
import TextField from '@mui/material/TextField';

import {StyledTextField} from '@app/components/dashboard/workspace-forms-tab-content';
import {SearchIcon} from '@app/components/icons/search';
import {placeHolder} from '@app/constants/locales/placeholder';
import cn from "classnames";

interface ISearchInputProps {
    handleSearch: (event: any) => void;
    className?: string
}

export default function SearchInput({handleSearch, className}: ISearchInputProps) {
    const {t} = useTranslation();
    const debouncedResults = useMemo(() => {
        return debounce(handleSearch, 500);
    }, []);

    return (
        <StyledTextField>
            <TextField
                sx={{height: '46px', padding: 0}}
                size="small"
                name="search-input"
                placeholder={t(placeHolder.search)}
                onChange={debouncedResults}
                className={cn('w-full bg-white focus:bg-white active:bg-white', className)}
                InputProps={{
                    sx: {
                        paddingLeft: '16px'
                    },
                    endAdornment: (
                        <InputAdornment sx={{padding: 0}} position="end">
                            <SearchIcon/>
                        </InputAdornment>
                    )
                }}
            />
        </StyledTextField>
    );
}
