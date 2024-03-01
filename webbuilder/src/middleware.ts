import { NextRequest, NextResponse } from 'next/server';

import environments from './configs/environments';

export async function middleware(request: NextRequest) {
    if (environments.AUTH_ENABLED) {
        const Authorization = request.cookies.get('Authorization')?.value;
        const RefreshToken = request.cookies.get('RefreshToken')?.value;

        const auth = !!Authorization ? `Authorization=${Authorization}` : '';
        const refresh = !!RefreshToken ? `RefreshToken=${RefreshToken}` : '';

        const config = {
            method: 'GET',
            headers: {
                cookie: `${auth};${refresh}`
            }
        };
        try {
            const statusResponse = await fetch(
                process.env.API_ENDPOINT_HOST + '/auth/status',
                config
            );
            const user = await statusResponse.json();
            if (statusResponse.status !== 200) {
                return NextResponse.redirect(new URL('/login', request.url));
            }
        } catch (e) {
            return NextResponse.redirect(new URL('/login', request.url));
        }
    }

    const response = NextResponse.next();
    return response;
}

export const config = {
    matcher: ['/((?!api|_next/static|_next/image|favicon.ico|login).*)']
};
