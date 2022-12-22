import React from 'react';

import Image from 'next/image';
import { Router, useRouter } from 'next/router';

import oop from 'public/oop.svg';

import Layout from '@app/layouts/_layout';

const Collector = () => {
    const router = useRouter();
    return (
        <Layout className="h-[100vh]" hideSignIn={true}>
            <div className="flex flex-col justify-between items-center my-auto">
                <div className="my-5 py-5">
                    <Image src={oop} className={'rounded-lg'} alt={'not a collector'} height={450} />
                </div>
                <div className="flex justify-between flex-col items-center gap-3">
                    <h1 className=" text-3xl font-bold lg:text-5xl">Oops!</h1>
                    <div className="flex flex-col justify-center items-center my-2">
                        <h3 className="text-[#007aff] text-lg font-medium lg:text-3xl">It seems like you are not into our form creator team.</h3>
                        <span className=" text-lg font-medium lg:text-2xl">Please become a form creator to use our service.</span>
                    </div>
                    <button onClick={() => router.push('https://forms.bettercollected.com/forms/become-a-better-collector')} className="bg-[#007AFF] px-8 py-3 rounded-md text-xl font-medium text-white active:bg-[#0061CB] my-5">
                        Become a better collector
                    </button>
                </div>
            </div>
        </Layout>
    );
};

export default Collector;
