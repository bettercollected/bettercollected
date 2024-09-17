import { NextApiRequest, NextApiResponse } from 'next';
import { createApi } from 'unsplash-js';

const unsplashAccessKey = process.env.UNSPLASH_ACCESS_KEY || '';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    const { page = '1', perPage = '30', query } = req.query;

    if (!unsplashAccessKey) {
        return res.status(400).json({ message: 'Missing Unsplash access key' });
    }

    if (!query) {
        return res.status(400).json({ message: 'Pass a query' });
    }
    try {
        const unsplash = createApi({ accessKey: unsplashAccessKey });

        const photos = await unsplash.search
            .getPhotos({
                page: parseInt(page as string, 10),
                perPage: parseInt(perPage as string, 10),
                query: (query as string) || '',
                orientation: 'landscape'
            })
            .then((response) => response.response);

        if (!photos) {
            return res.status(404).json({ message: 'No photos found' });
        }

        res.status(200).json(photos);
    } catch (error) {
        console.error(error);
        res.status(500).json({ message: 'Internal server error' });
    }
}
