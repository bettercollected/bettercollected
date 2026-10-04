import { NextResponse } from 'next/server';

import { createApi } from 'unsplash-js';

const unsplashAccessKey = process.env.UNSPLASH_ACCESS_KEY || '';

// Unsplash photo ids are short url-safe strings (e.g. "mtNweauBsMQ").
const PHOTO_ID = /^[A-Za-z0-9_-]{1,64}$/;

export async function POST(request: Request) {
    try {
        const photo: any = await request.json();
        const id = typeof photo?.id === 'string' ? photo.id : '';
        if (!PHOTO_ID.test(id)) {
            return NextResponse.json({ message: 'Invalid photo' }, { status: 400 });
        }
        const unsplash = createApi({ accessKey: unsplashAccessKey });
        const { data, error } = await unsplash.GET('/photos/{id}/download', { params: { path: { id } } });
        if (error) {
            return NextResponse.json({ error }, { status: 502 });
        }
        return NextResponse.json(data, { status: 200 });
    } catch (e) {
        console.log(e);
        return NextResponse.json({ error: e }, { status: 500 });
    }
}
