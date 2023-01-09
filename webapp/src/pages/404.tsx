import Link from 'next/link';

import Layout from '@app/layouts/_layout';

export default function FourOhFour() {
    return (
        <Layout hideSignIn className="min-h-screen">
            <div className="!min-h-screen w-full flex flex-col items-center justify-center">
                <h1>404 - Page Not Found</h1>

                <Link href="/">
                    <a className="text-blue-500 hover:underline">Go back home</a>
                </Link>
            </div>
        </Layout>
    );
}
