import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Pro from '@Components/Common/Icons/Dashboard/Pro';
import ModalButton from '@Components/Common/Input/Button/ModalButton';

import PlanCard from '@app/components/pro-plan/plan-card';
import ActiveLink from '@app/components/ui/links/active-link';
import Loader from '@app/components/ui/loader';
import Logo from '@app/components/ui/logo';
import environments from '@app/configs/environments';
import { buttonConstant } from '@app/constants/locales/button';
import { pricingPlan } from '@app/constants/locales/pricingplan';
import { upgradeConst } from '@app/constants/locales/upgrade';
import { selectAuthStatus } from '@app/store/auth/selectors';
import { useAppSelector } from '@app/store/hooks';
import { useGetPlansQuery } from '@app/store/plans/api';
import cn from 'classnames';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize } from '@Components/Common/Input/Button/AppButtonProps';
import { useSuggestPriceAndUpgradeUserToProMutation } from '@app/store/price-suggestion/api';
import { toast } from 'react-toastify';

export interface IUpgradeToProModal {
    featureText?: string;
    isModal?: boolean;
}


const prices = [
    0, 5, 15, 25, 50
];

export default function UpgradeToProContainer({ featureText, isModal = true }: IUpgradeToProModal) {
    const { data, isLoading } = useGetPlansQuery();
    const { t } = useTranslation();
    const [activePlan, setActivePlan] = useState<any>();
    const auth = useAppSelector(selectAuthStatus);

    const [suggestPrice, { isLoading: isSuggesting }] = useSuggestPriceAndUpgradeUserToProMutation();

    const [activeSuggestion, setActiveSuggestion] = useState<null | number>(null);
    const [customPrice, setCustomPrice] = useState('');

    useEffect(() => {
        if (data && Array.isArray(data) && data.length > 0) setActivePlan(data[0]);
    }, [data]);

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

    const url = auth === null ? '/login?fromProPlan=true' : `${environments.API_ENDPOINT_HOST}/stripe/session/create/checkout?price_id=${activePlan?.price_id}`;

    const onClickProTag = () => {
        if (isModal) return;
        if (auth === null) {
            router.push('https://bettercollected.com');
        } else {
            router.push('/login');
        }
    };
    return (
        <div className="container p-10  w-full h-full mx-auto flex flex-col items-center justify-center">
            <div className={`w-fit ${!isModal ? 'cursor-pointer' : ''}`} onClick={onClickProTag}>
                <div className="flex pb-10 items-center pointer-events-none">
                    <Logo />
                    <div
                        className="flex items-center rounded ml-1 gap-[2px] h-5 sm:h-6 p-1 sm:p-[6px] text-[10px] sm:body5 uppercase !leading-none !font-semibold !text-white bg-brand-500">
                        <Pro width={12} height={12} />
                        <span className="leading-none">Pro</span>
                    </div>
                </div>
            </div>

            {
                !environments.ENABLE_SUGGEST_PRICE ? (
                    <>

                        <div
                            className="h2-new text-black-900 font-semibold text-center mb-4 max-w-[370px]">{featureText || t(upgradeConst.features.default.slogan)}</div>
                        <div className="p2-new text-center mb-6 text-black-600">{t(pricingPlan.description)}</div>
                        {isLoading && <Loader variant="blink" />}

                        {data &&
                            Array.isArray(data) &&
                            data.map((plan: any) => (
                                <PlanCard
                                    activePlan={activePlan}
                                    plan={plan}
                                    key={plan.price_id}
                                    onClick={() => {
                                        setActivePlan(plan);
                                    }}
                                />
                            ))}

                        {data && (
                            <ActiveLink className="mt-10" href={url}>
                                <ModalButton>{t(buttonConstant.continue)}</ModalButton>
                            </ActiveLink>
                        )}
                    </>
                ) : (
                    <>
                        <div className="text-pink-500 mt-10 h5-new mb-6">
                            Help us set the price
                        </div>

                        <div className="h2-new text-center mb-2">
                            Suggest a monthly price for PRO
                        </div>
                        <div className="max-w-[314px] p2-new text-black-700 text-center">
                            Did you love the Pro features? Let us know how
                            much you value them!
                        </div>
                        <div className="mt-10 flex flex-wrap gap-2">
                            {
                                prices.map((price, index) => {
                                    return <div key={`${price}`} onClick={() => {
                                        setActiveSuggestion(price);
                                        setCustomPrice('');
                                    }}
                                                className={cn('w-[70px] h-10 flex items-center bg-black-100 cursor-pointer justify-center hover:text-black-800 ' +
                                                    'rounded-lg hover:border hover:border-blue-200 text-black-500' +
                                                    ' hover:bg-white', price === activeSuggestion && 'bg-white shadow-suggestion-price !text-black-800')}>
                                        ${price}
                                    </div>;
                                })
                            }
                            <div
                                className={cn('rounded-lg focus-within:shadow-suggestion-price h-10 border border-blue-100 flex',
                                    customPrice && 'shadow-suggestion-price'
                                )}>
                                <div
                                    className="bg-black-100 px-2 rounded-l-lg h-full w-full items-center justify-center flex text-black-500">
                                    $
                                </div>
                                <input type="number" contentEditable
                                       value={customPrice || ''}
                                       onFocus={() => {
                                           setActiveSuggestion(null);
                                       }}
                                       onChange={(event) => {
                                           setCustomPrice(event.target.value);
                                       }}
                                       className={cn('outline-none border-0 rounded-r-lg text-sm bg-white w-[82px] placeholder-black-500 font-medium !p-2 text-center')}
                                       placeholder="Amount" />
                            </div>

                        </div>
                        <div className="mt-10">
                            <AppButton isLoading={isSuggesting} className="mb-2" size={ButtonSize.Medium}
                                       onClick={async () => {
                                           if (!activeSuggestion && !customPrice) {
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

                                                   toast('Congratulations! You have been upgraded to PRO', { type: 'success' });
                                                   router.push(router.asPath);
                                               }
                                               if (response.error) {
                                                   toast('Something went wrong', {
                                                       type: 'error'
                                                   });
                                               }
                                           });
                                       }}>
                                Unlock Pro Features
                            </AppButton>
                            <div className="text-center p2-new text-black-600 italic">
                                Free for a limited time!
                            </div>
                        </div>
                    </>
                )
            }
            <div className="max-w-[658px]">
                <div className="text-xs mt-12 mb-2">{t(upgradeConst.proIncludes)}</div>
                <div className="grid grid-cols-1 md:grid-cols-2 w-full gap-6">
                    {features.map((feature: any, idx: number) => {
                        return (
                            <div key={feature.title + idx} style={{ background: feature.color }}
                                 className={`flex rounded-lg p-4 flex-col`}>
                                <div className="h4-new font-medium ">{feature.title}</div>

                                <div className="mt-2 p2-new">{feature.description}</div>
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}
