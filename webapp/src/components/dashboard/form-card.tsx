import React, { useEffect, useMemo, useState } from 'react';

import Router, { useRouter } from 'next/router';

import styled from '@emotion/styled';
import { IconButton, InputAdornment } from '@mui/material';
import TextField from '@mui/material/TextField';
import { useCookies } from 'react-cookie';
import { useDispatch } from 'react-redux';

import EmptyTray from '@app/assets/svgs/empty-tray.svg';
import { Logout } from '@app/components/icons/logout-icon';
import { SearchIcon } from '@app/components/icons/search';
import { ShareIcon } from '@app/components/icons/share-icon';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import Image from '@app/components/ui/image';
import ActiveLink from '@app/components/ui/links/active-link';
import MuiSnackbar from '@app/components/ui/mui-snackbar';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { useAppSelector } from '@app/store/hooks';
import { activeTabDataSlice } from '@app/store/search/activeTabDataSlice';
import { toEndDottedStr } from '@app/utils/stringUtils';

const StyledTextField = styled.div`
    .MuiFormControl-root {
        background: white;
        border-radius: 14px;
        outline: none;
        float: right;
    }

    .MuiOutlinedInput-notchedOutline {
        border-radius: 14px;
        border-width: 0.5px;
    }
`;

export default function FormCard() {
    const [isOpen, setIsOpen] = useState(false);
    const [_, copyToClipboard] = useCopyToClipboard();
    const [searchText, setSearchText] = useState('');

    const forms = useAppSelector((state) => state.activeData.formsArray);

    // useEffect(() => {
    //     // const filteredForms = getActiveTab.filter((form) => form.info.title.toLowerCase().includes(searchText.toLowerCase()));
    //     // if (!!companyJson) {
    //     //     const companyForms: Array<GoogleFormDto> | null = companyJson?.forms ?? [];
    //     //     const filteredForms = companyForms.filter((form) => form.info.title.toLowerCase().includes(searchText.toLowerCase()));
    //     //     timeOutId = setTimeout(() => setForms(filteredForms ?? []), 500);
    //     // }
    //     // return () => timeOutId && clearTimeout(timeOutId);
    // }, []);

    return (
        <>
            {/* <StyledTextField>
                <TextField
                    size="small"
                    name="search-input"
                    placeholder="Search forms..."
                    value={searchText}
                    onChange={() => {}}
                    className={'mt-5 xl:mt-9'}
                    // InputProps={{
                    //     endAdornment: (
                    //         <InputAdornment position="end">
                    //             <IconButton>
                    //                 <SearchIcon />
                    //             </IconButton>
                    //         </InputAdornment>
                    //     )
                    // }}
                />
            </StyledTextField> */}
            <div className="pt-3 md:pt-7">
                {forms.length === 0 && (
                    <div className="w-full min-h-[30vh] flex flex-col items-center justify-center text-darkGrey">
                        <Image src={EmptyTray} width={40} height={40} alt="Empty Tray" />
                        <p className="mt-4 p-0">0 forms</p>
                    </div>
                )}
                <div className="grid grid-cols-1 md:grid-cols-2 3xl:grid-cols-3 4xl:grid-cols-4 gap-8">
                    {forms.length !== 0 &&
                        forms.map((form: any) => {
                            const slug = form.info.title.toLowerCase().replaceAll(' ', '-');
                            let shareUrl = '';
                            if (window && typeof window !== 'undefined') {
                                shareUrl = `${window.location.origin}/forms/${slug}`;
                            }
                            return (
                                <ActiveLink
                                    key={form.id}
                                    href={{
                                        pathname: `/forms/[slug]`,
                                        query: { slug }
                                    }}
                                >
                                    <div className="flex flex-row items-center justify-between h-full gap-8 p-5 border-[1px] border-neutral-300 hover:border-blue-500 drop-shadow-sm hover:drop-shadow-lg transition cursor-pointer bg-white rounded-[20px]">
                                        <div className="flex flex-col justify-start h-full">
                                            <p className="text-xl text-grey mb-4 p-0">{form.info.title}</p>
                                            {form.info?.description && <p className="text-base text-softBlue m-0 p-0 w-full">{toEndDottedStr(form.info.description, 180)}</p>}
                                        </div>
                                        <div
                                            aria-hidden
                                            onClick={(event) => {
                                                event.preventDefault();
                                                event.stopPropagation();
                                                copyToClipboard(shareUrl);
                                                setIsOpen(true);
                                            }}
                                            className="p-2 border-[1px] border-white hover:border-neutral-100 hover:shadow rounded-md"
                                        >
                                            <ShareIcon width={19} height={19} />
                                        </div>
                                    </div>
                                </ActiveLink>
                            );
                        })}
                </div>
                <MuiSnackbar isOpen={isOpen} setIsOpen={setIsOpen} message="Copied URL" severity="info" />
            </div>
        </>
    );
}
