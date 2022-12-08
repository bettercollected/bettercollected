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

export default function ResponseCard() {
    const [isOpen, setIsOpen] = useState(false);
    const [_, copyToClipboard] = useCopyToClipboard();
    const [searchText, setSearchText] = useState('');

    // const forms = useAppSelector((state) => state.activeData.formsArray);

    // useEffect(() => {
    //     // const filteredForms = getActiveTab.filter((form) => form.info.title.toLowerCase().includes(searchText.toLowerCase()));
    //     // if (!!companyJson) {
    //     //     const companyForms: Array<GoogleFormDto> | null = companyJson?.forms ?? [];
    //     //     const filteredForms = companyForms.filter((form) => form.info.title.toLowerCase().includes(searchText.toLowerCase()));
    //     //     timeOutId = setTimeout(() => setForms(filteredForms ?? []), 500);
    //     // }
    //     // return () => timeOutId && clearTimeout(timeOutId);
    // }, []);

    const forms = [
        {
            id: '1RTwg2uQbv1X2xEiNgyWN8wizD3HCmWg1naYdyqSoYOQ',
            info: {
                title: 'Become a Better Responder',
                description:
                    'Loren Ipsum is great for collecting data from users via form responses but it lacks some important features for companies like us who value users data rights and privacy. For eg. once the user fills in the form, they cannot always view their own responses or see their past form responses. It feels like the user is ignored after the data is collected from them. We feel that is not right. There has to be a better way to collect data and let the user exercise their data rights.\n\nBetter Collected is exactly the platform for addressing that. Better Collected integrates with Google forms and opens up a portal for your users to view all of their collected data via Google forms and let them exercise rights like request for data deletion. This all happens without disrupting your normal workflow how you use Google forms. Better collected makes you a better data collector.\n\nFill the form below to join the waitlist so we get to inform you once the platform is ready for you. First 100 users to join the waitlist gets the Lifetime access to the platform for FREE.\n\nBonus: You can also use your own domain and generate custom URLs for your Google forms with our platform. No more random looking URLs. Instead, beautiful and branded forms. How cool is that?',
                documentTitle: 'Better Collected Waiting List'
            },
            revisionId: '00000176',
            responderUri: 'https://docs.google.com/forms/d/e/1FAIpQLSc-OA5vBjBLYm2xN2ZVxDuxqqrmwSHKAqAgv6QrF1TwIWKMow/viewform',
            items: [
                {
                    itemId: '7b268a27',
                    title: 'Your full name',
                    questionItem: {
                        question: {
                            questionId: '3bb27f24',
                            required: true,
                            textQuestion: {}
                        }
                    }
                },
                {
                    itemId: '470e4740',
                    title: 'Your organization (or website)',
                    questionItem: {
                        question: {
                            questionId: '353705f2',
                            textQuestion: {}
                        }
                    }
                },
                {
                    itemId: '593a828b',
                    title: 'We regularly share our weekly progress with our users via email and on Twitter. Would you like to receive those weekly progress emails?',
                    questionItem: {
                        question: {
                            questionId: '1c19cd1b',
                            required: true,
                            choiceQuestion: {
                                type: 'RADIO',
                                options: [
                                    {
                                        value: 'Yes'
                                    },
                                    {
                                        value: "Nah, I'll wait until the platform is ready to use"
                                    }
                                ]
                            }
                        }
                    }
                },
                {
                    itemId: '27dfcc29',
                    title: 'Would you like to register to be beta tester who gets to use the new features before anybody else?',
                    questionItem: {
                        question: {
                            questionId: '57b6012a',
                            required: true,
                            choiceQuestion: {
                                type: 'RADIO',
                                options: [
                                    {
                                        value: 'Yes'
                                    },
                                    {
                                        value: "Nah, I'll wait until the platform is fully ready"
                                    }
                                ]
                            }
                        }
                    }
                },
                {
                    itemId: '7ed4ab90',
                    title: 'Do you have a feature request, suggestion or feedback that you would like to share with us?',
                    questionItem: {
                        question: {
                            questionId: '657b2d88',
                            textQuestion: {
                                paragraph: true
                            }
                        }
                    }
                }
            ]
        }
    ];

    return (
        <>
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
                                        pathname: `/submissions/[slug]`,
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
