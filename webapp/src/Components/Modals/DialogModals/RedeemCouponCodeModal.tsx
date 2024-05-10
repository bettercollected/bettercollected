import React, { useState } from 'react';

import { useRouter } from 'next/router';

import CircularCheck from '@Components/Common/Icons/Common/CircularCheck';
import AppTextField from '@Components/Common/Input/AppTextField';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize } from '@Components/Common/Input/Button/AppButtonProps';
import CloseModal from '@Components/Modals/CloseModal';

import { useModal } from '@app/components/modal-views/context';
import { ProLogo } from '@app/components/ui/logo';
import environments from '@app/configs/environments';
import { useRedeemCouponCodeMutation } from '@app/store/coupon-code/api';
import { fireworks } from '@app/utils/confetti';
import BetterCollectedLogo from '@app/views/atoms/Icons/BetterCollectedLogo';

export default function RedeemCouponCodeModal({ showSuccess = false }: { showSuccess?: boolean }) {
    const [error, setError] = useState('');
    const { openModal, closeModal } = useModal();

    const [redeemCode, setRedeemCode] = useState('');

    const [redeemCouponReward, { isLoading }] = useRedeemCouponCodeMutation();

    const router = useRouter();

    const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        if (!redeemCode) return;
        const response: any = await redeemCouponReward({ code: redeemCode });
        if (response.data) {
            fireworks();
            router.push(router.asPath, undefined, { shallow: true }).then(() => {
                openModal('REDEEM_CODE_MODAL', { showSuccess: true });
            });
        }
        if (response.error) {
            setError('Invalid coupon code');
        }
    };

    return (
        <div className="relative flex flex-col items-center justify-center rounded-md bg-white px-5 pb-10 pt-8 lg:min-w-[600px]">
            <CloseModal />
            <div className="pointer-events-none flex items-center">
                <BetterCollectedLogo className="h-[19px]" />
                <ProLogo />
            </div>
            {showSuccess ? (
                <>
                    <CircularCheck className="mb-2 mt-12" height={41} width={41} />
                    <div className="h3-new mb-2">Congratulations!</div>
                    <div className="p2-new text-black-700 mb-10 max-w-[420px] !text-center">Your code has been successfully redeemed, and your account is now upgraded to PRO.</div>
                    <AppButton
                        size={ButtonSize.Medium}
                        className="min-w-[120px]"
                        onClick={() => {
                            closeModal();
                        }}
                    >
                        Done
                    </AppButton>
                </>
            ) : (
                <>
                    <div className="h3-new mb-2 mt-12">Lifetime PRO deal</div>
                    <div className="p3-new text-black-700 mb-8 max-w-[424px] text-center text-sm">
                        Redeem your AppSumo coupon code for lifetime access to BetterCollected PRO or visit AppSumo to{' '}
                        <a href={environments.APP_SUMO_PRODUCT_URL} target="_blank" rel="noreferrer" className="text-brand-500 cursor-pointer">
                            get the code
                        </a>
                        .
                    </div>
                    <div className="mb-12 flex flex-col gap-2">
                        <div>PRO includes:</div>
                        <div className="flex items-center gap-2">
                            <CircularCheck height={20} width={20} color="#B8D5FF" />
                            <span>Unlimited Forms</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <CircularCheck height={20} width={20} color="#B8D5FF" />
                            <span>Custom Domain Name</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <CircularCheck height={20} width={20} color="#B8D5FF" />
                            <span>Multiple Workspaces</span>
                        </div>
                    </div>
                    <form className="flex gap-4" onSubmit={onSubmit}>
                        <div>
                            <AppTextField
                                value={redeemCode}
                                onChange={(event) => {
                                    setError('');
                                    setRedeemCode(event.target.value);
                                }}
                                placeholder="Enter your coupon code"
                            />
                            <div className="mt-2 h-[18px] text-left text-sm text-red-500">{error && error}</div>
                        </div>
                        <AppButton type="submit" className="min-w-[120px]" isLoading={isLoading} size={ButtonSize.Medium}>
                            {' '}
                            Redeem{' '}
                        </AppButton>
                    </form>
                </>
            )}
        </div>
    );
}
