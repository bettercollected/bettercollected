import { rest } from 'msw';

import { workspaceMock } from '@app/mock/data/workspace-mock';

export const workspace_handlers = [
    rest.get('http://localhost:8000/workspaces/:workspace_id', (req, res, context) => {
        return res(
            context.json({
                payload: {
                    content: workspaceMock
                }
            })
        );
    }),
    rest.get('http://localhost:8000/workspaces/mine', (req, res, context) => {
        return res(
            context.json({
                payload: {
                    content: [workspaceMock]
                }
            })
        );
    }),
    rest.post('http://localhost:8000/workspaces', (req, res, context) => {
        return res(
            context.json({
                payload: {
                    content: workspaceMock
                }
            })
        );
    }),
    rest.patch('http://localhost:8000/workspaces/:workspace_id', (req, res, context) => {
        return res(
            context.json({
                payload: {
                    content: workspaceMock
                }
            })
        );
    }),
    rest.patch('http://localhost:8000/workspaces/:workspace_id/theme', (req, res, context) => {
        return res(
            context.json({
                payload: {
                    content: workspaceMock
                }
            })
        );
    }),
    rest.patch('http://localhost:8000/workspaces/:workspace_id/policies', (req, res, context) => {
        return res();
    }),
    rest.delete('http://localhost:8000/workspaces/:workspace_id/custom_domain', (req, res, context) => {
        return res(
            context.json({
                payload: {
                    content: workspaceMock
                }
            })
        );
    })
];
