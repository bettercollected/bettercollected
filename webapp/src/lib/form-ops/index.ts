/**
 * Form ops engine (pure TypeScript, no React): the builder's twin of the
 * backend's ops engine (backend/app/services/ai/ops.py).
 *
 *   const { doc, results, inverse } = applyOps(form, ops, { atomic: true });
 */
export { applied, applyOps, finishDoc, tooManyOps } from './apply';
export { compactOps } from './compact';
export { entityDiff } from './entity-diff';
export { EDITOR_ONLY_OPS, OP_NAMES } from './handlers';
export { applySettingsPatch } from './handlers/form';
export { buildInverse, touchedEntities } from './inverse';
export { MAX_FIELDS, MAX_OPS_PER_BATCH, MAX_PAGES, OpError } from './model';
export { refDependencies } from './refs';
export type * from './types';
