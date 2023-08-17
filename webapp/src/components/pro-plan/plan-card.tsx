import React from 'react';

import { useTranslation } from 'next-i18next';

import _ from 'lodash';

import Radio from '@mui/material/Radio';

import { localesCommon } from '@app/constants/locales/common';
import { Plan } from '@app/store/plans/types';

interface IPlanCardProps {
    plan: Plan;
    activePlan: Plan;
    onClick: () => void;
}

export default function PlanCard({ plan, activePlan, onClick }: IPlanCardProps) {
    const active = activePlan?.price_id === plan.price_id;
    const { t } = useTranslation();

    const currency = plan.currency === 'eur' ? '€' : '$';
    const interval = _.capitalize(plan.recurring_interval) + 'ly';
    return (
        <div onClick={onClick} className={` flex cursor-pointer mb-2 items-center justify-between px-5 py-4 rounded-lg border w-full max-w-[433px] min-h-[86px] hover:border-brand-400  ${active ? 'border-brand-400' : 'border-black-400'}`}>
            <div className="flex items-center">
                <div>
                    <Radio
                        sx={{
                            '& .MuiSvgIcon-root': {
                                fontSize: 32
                            }
                        }}
                        checked={active}
                        size="medium"
                    />
                </div>
                <div>
                    <div className={`sh1 ${!active ? '!text-black-500' : ''}`}>{interval}</div>
                    {plan.recurring_interval === 'year' && <div className={`body1 ${!active ? '!text-black-500' : '!text-[#E79B0B]'}  `}>{t(localesCommon.save)} 17%</div>}
                </div>
            </div>

            <div className={`h3 ${!active ? '!text-black-500' : ''}`}>
                {currency}
                {plan.price}
            </div>
        </div>
    );
}
