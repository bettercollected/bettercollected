/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-22
 * Time: 09:38
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
import { useRouter } from 'next/router';

import { LongArrowLeft } from '@app/components/icons/long-arrow-left';
import Button from '@app/components/ui/button';
import environments from '@app/configs/environments';

export default function Waitlist() {
    const router = useRouter();

    return (
        <>
            <Button className="w-auto z-10 !h-8 mx-4 mt-0 sm:mt-1 md:mt-3 hover:!-translate-y-0 focus:-translate-y-0" variant="solid" onClick={() => router.push('/')}>
                <LongArrowLeft width={15} height={15} />
            </Button>
            <div className={'absolute left-0 right-0 top-0 bottom-0'}>
                <iframe src={environments.WAITLIST_FORM_URL} height={'100%'} width={'100%'}>
                    Loading…
                </iframe>
            </div>
        </>
    );
}
