import React from 'react';

import Image from 'next/image';

import oop from 'public/oop.svg';

import Layout from '@app/layouts/_layout';

const Error = () => {
    return (
        <Layout className="min-h-screen">
            <div className="flex !h-full flex-col justify-between items-center my-auto">
                <div className="my-5 py-5">
                    <Image src={oop} className={'rounded-lg'} alt={'Error page'} height={450} />
                </div>
                <div className="flex justify-between flex-col items-center gap-3">
                    <h1 className=" text-3xl text-blue-500 font-bold lg:text-4xl">Oops! Something went wrong</h1>
                    <div className="flex flex-col justify-center items-center my-2">
                        <h3 className="text-gray-500 text-lg font-medium lg:text-2xl">Please try again later.</h3>
                    </div>
                </div>
            </div>
        </Layout>
    );
};

export default Error;
