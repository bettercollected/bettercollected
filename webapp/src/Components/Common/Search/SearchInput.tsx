import { useMemo } from 'react';

import { useTranslation } from 'next-i18next';

import { debounce } from 'lodash';

import { InputAdornment } from '@mui/material';
import TextField from '@mui/material/TextField';
import cn from 'classnames';

import { StyledTextField } from '@app/components/dashboard/workspace-forms-tab-content';
import { SearchIcon } from '@app/components/icons/search';
import { placeHolder } from '@app/constants/locales/placeholder';


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
        <StyledTextField>
            <TextField
                size="small"
                name="search-input"
                placeholder={placeholder ? placeholder : t(placeHolder.search)}
                onChange={debouncedResults}
                className={cn('w-full bg-white focus:bg-white active:bg-white', className)}
                sx={{
                    height: '40px',
                    padding: 0,
                    '& .MuiOutlinedInput-root': {
                        '&.Mui-focused fieldset': {
                            borderColor: '#B8E8FF',
                            boxShadow: '0px 0px 12px 0px rgba(7, 100, 235, 0.45)'
                        }
                    }
                }}
                InputProps={{
                    sx: {
                        paddingLeft: '16px',
                        backgroundColor: '#FFFFFF'
                    },
                    startAdornment: (
                        <InputAdornment sx={{ padding: 0 }} position="start">
                            <SearchIcon className="text-black-900 stroke-2" />
                        </InputAdornment>
                    )
                }}
            />
        </StyledTextField>
    );
}