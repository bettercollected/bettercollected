This is a [Next.js](https://nextjs.org/) project bootstrapped with [`create-next-app`](https://github.com/vercel/next.js/tree/canary/packages/create-next-app).

## Better Collected
Better collected is a platform that enables form creators to open a portal for their form submitters to see their collected data and let them exercise their data rights.

## Running locally
 Open your favorite code editor. Webstorm is recommended.

**Step 1:** Install all the required packages using below command.
```bash
npm install
```
**Step 2:** Create a .env.local file in your root directory and copy the contents of .env.example to .env.local using below command
```bash
cp .env.example .env.local
```
the environment variables inside .env.local will be injected to nextjs project on run time.

**Step 3:** Run the development server:

```bash
npm run dev
# or
yarn dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

The starting point for the application is `pages/index.tsx`.

[API routes](https://nextjs.org/docs/api-routes/introduction) can be accessed on [http://localhost:3000/api/hello](http://localhost:3000/api/hello). This endpoint can be edited in `pages/api/hello.ts`.

The `pages/api` directory is mapped to `/api/*`. Files in this directory are treated as [API routes](https://nextjs.org/docs/api-routes/introduction) instead of React pages.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js/) - your feedback and contributions are welcome!
