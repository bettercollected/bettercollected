import type { ReactElement, ReactNode } from 'react';

import type { NextPage } from 'next';

export type NextPageWithLayout<P = {}> = NextPage<P> & {
    authorization?: boolean;
    getLayout?: (page: ReactElement) => ReactNode;
};
