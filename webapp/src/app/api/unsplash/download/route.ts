import { NextResponse } from 'next/server';
import { createApi } from 'unsplash-js';

const unsplashAccessKey = process.env.UNSPLASH_ACCESS_KEY || '';

export async function POST(request: Request) {
    try {
        const photo: any = await request.json();
        const unsplash = createApi({ accessKey: unsplashAccessKey });
        const response = await unsplash.photos.trackDownload({ downloadLocation: photo.links.download_location });
        return NextResponse.json(response, { status: 200 });
    } catch (e) {
        console.log(e);
        return NextResponse.json({ error: e }, { status: 500 });
    }
}
