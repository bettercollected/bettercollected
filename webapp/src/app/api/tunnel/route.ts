import { NextResponse } from 'next/server';
import * as Sentry from '@sentry/nextjs';
import * as url from 'url';

// Change host appropriately if you run your own Sentry instance.
const sentryHost = 'sentry.sireto.io';

// Set knownProjectIds to an array with your Sentry project IDs which you
// want to accept through this proxy.
const knownProjectIds: Array<any> = ['/24'];

export async function POST(request: Request) {
    try {
        const envelope = await request.text();
        const pieces = envelope.split('\n');

        const header = JSON.parse(pieces[0]);

        const { host, path } = url.parse(header.dsn);
        if (host !== sentryHost) {
            throw new Error(`Invalid host: ${host}`);
        }

        const projectId = path?.endsWith('/') ? path.slice(0, -1) : path;
        if (!knownProjectIds.includes(projectId)) {
            throw new Error(`Invalid project id: ${projectId}`);
        }

        const urlStr: string = `https://${sentryHost}/api${projectId}/envelope/?sentry_key=1cb86113299744a89248dbbc4abcf2e7`;
        const response = await fetch(urlStr, {
            method: 'POST',
            body: envelope
        }).catch((err) => {
            throw new Error(`API call stalled: ${err}`);
        });

        const data = await response.json();
        return NextResponse.json(data, { status: 200 });
    } catch (e) {
        Sentry.captureException(e);
        return NextResponse.json({ status: 'Invalid request' }, { status: 200 });
    }
}
