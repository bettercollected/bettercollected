import { rest } from 'msw';

export const workspace_responses_handlers = [
    rest.get('http://localhost:8080/workspaces/:workspace_id/submissions', (req, res, context) => {
        return res();
    }),
    rest.get('http://localhost:8080/workspaces/:workspace_id/allSubmissions', (req, res, context) => {
        return res();
    }),
    rest.get('http://localhost:8080/workspaces/:workspace_id/submissions/:submission_id', (req, res, context) => {
        return res();
    })
];
