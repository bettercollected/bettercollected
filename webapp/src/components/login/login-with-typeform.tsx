import Image from 'next/image';

import { Google } from '@app/components/icons/brands/google';
import environments from '@app/configs/environments';

export default function ConnectWithTypeForm() {
    return (
        <a href={`${environments.API_ENDPOINT_HOST}/auth/typeform/oauth?creator=true`} referrerPolicy="unsafe-url" className={`bg-black hover:bg-gray-800 max-w-[250px] mx-auto flex w-full items-center rounded-2xl p-[2px]`}>
            <div className="rounded-full border h-[24px] w-[28px] border-white relative">
                <Image src="/tf.png" className="rounded-full" layout="fill" alt={'T'} />
            </div>

            <div className="flex items-center py-1 w-full justify-center font-bold text-white text-[12px]">Login with Typeform</div>
        </a>
    );
}
