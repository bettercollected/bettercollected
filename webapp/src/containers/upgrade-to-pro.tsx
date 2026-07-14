"use client";

import { useState } from 'react';

import { useTranslation } from 'react-i18next';

import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import Logo, { ProLogo } from '@app/components/ui/logo';
import { upgradeConst } from '@app/constants/locales/upgrade';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { selectAuthStatus } from '@app/store/auth/selectors';
import { useAppSelector } from '@app/store/hooks';
import { useSuggestPriceAndUpgradeUserToProMutation } from '@app/store/price-suggestion/api';
import cn from 'classnames';
import { useRouter } from 'next/navigation';

interface IUpgradeToProModal {
    featureText?: string;
    isModal?: boolean;
    callback?: () => void;
}

const prices = [0, 5, 15, 25, 50];

export default function UpgradeToProContainer({ featureText, isModal = true, callback }: IUpgradeToProModal) {
    const { toast } = useToast();
    const { t } = useTranslation();
    const auth = useAppSelector(selectAuthStatus);

    const [suggestPrice, { isLoading: isSuggesting }] = useSuggestPriceAndUpgradeUserToProMutation();

    const [activeSuggestion, setActiveSuggestion] = useState<null | number>(null);
    const [customPrice, setCustomPrice] = useState('');

    const { closeModal } = useFullScreenModal();

    // One calm treatment for every card — the pastel-rainbow tints were the
    // "playful" palette the trust language retires (Design-Language §1).
    // Unlimited forms is NOT listed — forms and responses are free for
    // everyone, so it can't be a Pro differentiator.
    const features = [
        {
            title: t(upgradeConst.features.customDomain.title),
            description: t(upgradeConst.features.customDomain.description)
        },
        {
            title: t(upgradeConst.features.collaborator.title),
            description: t(upgradeConst.features.collaborator.description)
        },
        {
            title: t(upgradeConst.features.workspace.title),
            description: t(upgradeConst.features.workspace.description)
        }
    ];
    const router = useRouter();

    const onClickProTag = () => {
        if (isModal) return;
        if (auth === null) {
            router.push('https://bettercollected.com');
        } else {
            router.push('/login');
        }
    };
    return (
        <div className="container mx-auto flex h-full w-full flex-col items-center justify-center px-5 pb-10">
            <div className={`w-fit ${!isModal ? 'cursor-pointer' : ''}`} onClick={onClickProTag}>
                <div className="pointer-events-none flex items-center pb-10">
                    <Logo />
                    <ProLogo />
                </div>
            </div>
            <>
                {/* One honest claim, stated once. The old copy said "is Free"
                    up top and "Free for 90 days!" at the bottom — but the
                    upgrade has no expiry in code, so the 90-day line was a
                    surprise waiting to be discovered (Design-Language §5). */}
                <div className="h2-new mb-2 text-center">
                    bettercollected PRO is <span className="text-[#2456CC]">currently free</span>
                </div>
                <div className="p2-new text-black-700 max-w-[426px] text-center">No card needed and nothing is charged. Tell us what PRO would be worth to you — future pricing will be based on these suggestions.</div>
                <div className="mt-10 flex flex-wrap justify-center gap-2">
                    {prices.map((price, index) => {
                        return (
                            <div
                                tabIndex={0}
                                key={`${price}`}
                                onClick={() => {
                                    setActiveSuggestion(price);
                                    setCustomPrice('');
                                }}
                                className={cn(
                                    'bg-black-100 hover:text-black-800 flex h-10 w-[70px] cursor-pointer items-center justify-center font-medium ' + 'text-black-500 rounded-lg hover:border hover:border-[#A8C0EA]' + ' hover:bg-white',
                                    price === activeSuggestion && 'shadow-suggestion-price !text-black-800 bg-white'
                                )}
                            >
                                ${price}
                            </div>
                        );
                    })}
                    <div className={cn('focus-within:shadow-suggestion-price hidden h-10 rounded-lg border border-black-300 lg:flex', customPrice && 'shadow-suggestion-price')}>
                        <div className="bg-black-100 text-black-500 flex h-full w-full items-center justify-center rounded-l-lg px-2">$</div>
                        <input
                            type="number"
                            value={customPrice || ''}
                            onFocus={() => {
                                setActiveSuggestion(null);
                            }}
                            onChange={(event) => {
                                setCustomPrice(event.target.value);
                            }}
                            className={cn('placeholder-black-500 w-[82px] rounded-r-lg border-0 bg-white !p-2 text-left text-sm font-medium outline-none')}
                            placeholder="Amount"
                        />
                    </div>
                </div>
                <div className="mt-10">
                    <Button
                        disabled={isSuggesting}
                        className="mb-2"
                        onClick={async () => {
                            if (activeSuggestion === null && !customPrice) {
                                toast({ description: 'Please select a price first' });
                                return;
                            }
                            let price = 0;
                            if (activeSuggestion) {
                                price = activeSuggestion;
                            }
                            if (customPrice) {
                                price = parseInt(customPrice);
                            }
                            suggestPrice({
                                price
                            }).then((response: any) => {
                                if (response.data) {
                                    closeModal();
                                    if (callback) {
                                        callback();
                                    } else {
                                        router.refresh();
                                    }
                                    toast({ description: 'Congratulations! You have been upgraded to PRO' });
                                }
                                if (response.error) {
                                    // Say what actually failed — a 503 "Service is
                                    // not enabled" is actionable; "Something went
                                    // wrong" is not.
                                    toast({
                                        description: typeof response.error?.data === 'string' ? response.error.data : 'Could not activate PRO — please try again.',
                                        variant: 'destructive'
                                    });
                                }
                            });
                        }}
                    >
                        Activate PRO for free
                    </Button>
                </div>
            </>
            {/* )} */}
            <div className="max-w-[658px]">
                <div className="mb-2 mt-12 text-xs">{t(upgradeConst.proIncludes)}</div>
                <div className="grid w-full grid-cols-1 gap-4 md:grid-cols-2">
                    {features.map((feature: any, idx: number) => {
                        return (
                            <div key={feature.title + idx} className="border-black-300 bg-black-100 flex flex-col rounded-lg border p-4">
                                <div className="h4-new font-medium ">{feature.title}</div>

                                <div className="p2-new text-black-700 mt-2">{feature.description}</div>
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}
