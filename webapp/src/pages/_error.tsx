import { NextPageContext } from 'next';
import NextErrorComponent from 'next/error';

import * as Sentry from '@sentry/nextjs';

import { ClientSideException } from '@app/utils/errorAndExceptions';


const Error = ({ statusCode, hasGetInitialPropsRun, err }: any) => {
    if (!hasGetInitialPropsRun && err) {
        // getInitialProps is not called in case of
        // https://github.com/vercel/next.js/issues/8592. As a workaround, we pass
        // err via _app.js so it can be captured
        try {
            Sentry.captureException(err);
        } catch (e) {
            console.log('Error Sending Exception to Sentry');
        }
        // Flushing is not required in this case as it only happens on the client
    }

    return <NextErrorComponent statusCode={statusCode} />;
};

Error.getInitialProps = async (_context: NextPageContext) => {
    const errorInitialProps: any = await NextErrorComponent.getInitialProps(_context);

    // Workaround for https://github.com/vercel/next.js/issues/8592, mark when
    // getInitialProps has run
    errorInitialProps.hasGetInitialPropsRun = true;

    // Running on the server, the response object (`res`) is available.
    //
    // Next.js will pass an err on the server if a page's data fetching methods
    // threw or returned a Promise that rejected
    //
    // Running on the client (browser), Next.js will provide an err if:
    //
    //  - a page's `getInitialProps` threw or returned a Promise that rejected
    //  - an exception was thrown somewhere in the React lifecycle (render,
    //    componentDidMount, etc) that was caught by Next.js's React Error
    //    Boundary. Read more about what types of exceptions are caught by Error
    //    Boundaries: https://reactjs.org/docs/error-boundaries.html
    try {
        if (_context?.err) {
            Sentry.captureException(_context.err);

            // Flushing before returning is necessary if deploying to Vercel, see
            // https://vercel.com/docs/platform/limits#streaming-responses
            await Sentry.flush(2000);

            return errorInitialProps;
        }

        // If this point is reached, getInitialProps was called without any
        // information about what the error might be. This is unexpected and may
        // indicate a bug introduced in Next.js, so record it in Sentry

        Sentry.captureException(new ClientSideException(`_error.tsx getInitialProps missing data at path: ${_context?.asPath}`));
        await Sentry.flush(2000);
    } catch (e) {
        console.log('Error Sending error logs to sentry');
    }

    return errorInitialProps;
};

export default Error;