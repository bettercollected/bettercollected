import { NextResponse } from 'next/server';
import { createApi } from 'unsplash-js';

const unsplashAccessKey = process.env.UNSPLASH_ACCESS_KEY || '';

export async function GET(request: Request) {
    const { searchParams } = new URL(request.url);
    const page = searchParams.get('page') || '1';
    const perPage = searchParams.get('perPage') || '30';
    const query = searchParams.get('query');

    if (!unsplashAccessKey) {
        return NextResponse.json({ message: 'Missing Unsplash access key' }, { status: 400 });
    }

    if (!query) {
        return NextResponse.json({ message: 'Pass a query' }, { status: 400 });
    }

    try {
        const unsplash = createApi({ accessKey: unsplashAccessKey });

        const photos = await unsplash.search
            .getPhotos({
                page: parseInt(page, 10),
                perPage: parseInt(perPage, 10),
                query: query || '',
                orientation: 'landscape'
            })
            .then((response) => response.response);

        if (!photos) {
            return NextResponse.json({ message: 'No photos found' }, { status: 404 });
        }

        return NextResponse.json(photos, { status: 200 });
    } catch (error) {
        console.error(error);
        return NextResponse.json({ message: 'Internal server error' }, { status: 500 });
    }
}
