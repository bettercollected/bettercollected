import { useState } from 'react';

import { useTranslation } from 'next-i18next';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize } from '@Components/Common/Input/Button/AppButtonProps';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import Logo, { ProLogo } from '@app/components/ui/logo';
import { upgradeConst } from '@app/constants/locales/upgrade';
import { selectAuthStatus } from '@app/store/auth/selectors';
import { useAppSelector } from '@app/store/hooks';
import { useSuggestPriceAndUpgradeUserToProMutation } from '@app/store/price-suggestion/api';
import cn from 'classnames';
import { useRouter } from 'next/navigation';
import { toast } from 'react-toastify';

export interface IUpgradeToProModal {
    featureText?: string;
    isModal?: boolean;
    callback?: () => void;
}

const prices = [0, 5, 15, 25, 50];

export default function UpgradeToProContainer({ featureText, isModal = true, callback }: IUpgradeToProModal) {
    const { t } = useTranslation();
    const auth = useAppSelector(selectAuthStatus);

    const [suggestPrice, { isLoading: isSuggesting }] = useSuggestPriceAndUpgradeUserToProMutation();

    const [activeSuggestion, setActiveSuggestion] = useState<null | number>(null);
    const [customPrice, setCustomPrice] = useState('');

    const { closeModal } = useFullScreenModal();

    const features = [
        {
            title: t(upgradeConst.features.unlimitedForms.title),
            description: t(upgradeConst.features.unlimitedForms.description),
            color: '#E5EFFF'
        },
        {
            title: t(upgradeConst.features.customDomain.title),
            description: t(upgradeConst.features.customDomain.description),
            color: '#FFE8F0'
        },
        {
            title: t(upgradeConst.features.collaborator.title),
            description: t(upgradeConst.features.collaborator.description),
            color: '#E4FFF4'
        },
        {
            title: t(upgradeConst.features.workspace.title),
            description: t(upgradeConst.features.workspace.description),
            color: '#FFF7E9'
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
                <div className="h2-new mb-2 text-center">
                    bettercollected PRO is <span className="text-new-pink">Free</span>
                </div>
                <div className="p2-new text-black-700 max-w-[426px] text-center">You won't be charged any money. Share your thoughts on what the best price would be. Future pricing will be based on your suggestions.</div>
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
                                    'bg-black-100 hover:text-black-800 flex h-10 w-[70px] cursor-pointer items-center justify-center font-medium ' + 'text-black-500 rounded-lg hover:border hover:border-blue-200' + ' hover:bg-white',
                                    price === activeSuggestion && 'shadow-suggestion-price !text-black-800 bg-white'
                                )}
                            >
                                ${price}
                            </div>
                        );
                    })}
                    <div className={cn('focus-within:shadow-suggestion-price hidden h-10 rounded-lg border border-blue-100 lg:flex', customPrice && 'shadow-suggestion-price')}>
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
                    <AppButton
                        isLoading={isSuggesting}
                        className="mb-2"
                        size={ButtonSize.Medium}
                        onClick={async () => {
                            if (activeSuggestion === null && !customPrice) {
                                toast('Please select a price first', { type: 'warning' });
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
                                    toast('Congratulations! You have been upgraded to PRO', { type: 'success' });
                                }
                                if (response.error) {
                                    toast('Something went wrong', {
                                        type: 'error'
                                    });
                                }
                            });
                        }}
                    >
                        Start Pro account
                    </AppButton>
                    <div className="p2-new text-black-600 text-center italic">Free for 90 days!</div>
                </div>
            </>
            {/* )} */}
            <div className="max-w-[658px]">
                <div className="mb-2 mt-12 text-xs">{t(upgradeConst.proIncludes)}</div>
                <div className="grid w-full grid-cols-1 gap-4 md:grid-cols-2">
                    {features.map((feature: any, idx: number) => {
                        return (
                            <div key={feature.title + idx} style={{ background: feature.color }} className={`flex flex-col rounded-lg p-4`}>
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
