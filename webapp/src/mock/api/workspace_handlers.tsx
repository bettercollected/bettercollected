import { rest } from 'msw';

export const workspace_handlers = [
    rest.get('http://localhost:8000/workspaces/:workspace_id', (req, res, ctx) => {
        return res();
    }),
    rest.get('http://localhost:8000/workspaces/mine', (req, res, ctx) => {
        return res();
    }),
    rest.post('http://localhost:8000/workspaces', (req, res, context) => {
        return res();
    }),
    rest.patch('http://localhost:8000/workspaces/:workspace_id', (req, res, context) => {
        return res();
    }),
    rest.patch('http://localhost:8000/workspaces/:workspace_id/theme', (req, res, context) => {
        return res();
    }),
    rest.patch('http://localhost:8000/workspaces/:workspace_id/policies', (req, res, context) => {
        return res();
    }),
    rest.delete('http://localhost:8000/workspaces/:workspace_id/custom_domain', (req, res, context) => {
        return res();
    })
];
