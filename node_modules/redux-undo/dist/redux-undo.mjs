const c = {
  UNDO: "@@redux-undo/UNDO",
  REDO: "@@redux-undo/REDO",
  JUMP_TO_FUTURE: "@@redux-undo/JUMP_TO_FUTURE",
  JUMP_TO_PAST: "@@redux-undo/JUMP_TO_PAST",
  JUMP: "@@redux-undo/JUMP",
  CLEAR_HISTORY: "@@redux-undo/CLEAR_HISTORY"
}, M = {
  undo() {
    return { type: c.UNDO };
  },
  redo() {
    return { type: c.REDO };
  },
  jumpToFuture(e) {
    return { type: c.JUMP_TO_FUTURE, index: e };
  },
  jumpToPast(e) {
    return { type: c.JUMP_TO_PAST, index: e };
  },
  jump(e) {
    return { type: c.JUMP, index: e };
  },
  clearHistory() {
    return { type: c.CLEAR_HISTORY };
  }
};
function U(e, t = []) {
  return Array.isArray(e) ? e : typeof e == "string" ? [e] : t;
}
function E(e) {
  return typeof e.present < "u" && typeof e.future < "u" && typeof e.past < "u" && Array.isArray(e.future) && Array.isArray(e.past);
}
function v(e) {
  const t = U(e);
  return (n) => t.indexOf(n.type) >= 0;
}
function D(e) {
  const t = U(e);
  return (n) => t.indexOf(n.type) < 0;
}
function w(...e) {
  return e.reduce(
    (t, n) => (s, l, i) => t(s, l, i) && n(s, l, i),
    () => !0
  );
}
function B(e) {
  const t = U(e);
  return (n) => t.indexOf(n.type) >= 0 ? n.type : null;
}
function T(e, t, n, s = null) {
  return {
    past: e,
    present: t,
    future: n,
    group: s,
    _latestUnfiltered: t,
    index: e.length,
    limit: e.length + n.length + 1
  };
}
let _, d;
const P = {
  prevState: "#9E9E9E",
  action: "#03A9F4",
  nextState: "#4CAF50"
};
function F() {
  d = {
    header: [],
    prev: [],
    action: [],
    next: [],
    msgs: []
  };
}
function H() {
  const { header: e, prev: t, next: n, action: s, msgs: l } = d;
  console.group ? (console.groupCollapsed(...e), console.log(...t), console.log(...s), console.log(...n), console.log(...l), console.groupEnd()) : (console.log(...e), console.log(...t), console.log(...s), console.log(...n), console.log(...l));
}
function S(e, t, n) {
  return [
    `%c${e}`,
    `color: ${t}; font-weight: bold`,
    n
  ];
}
function h(e, t) {
  F(), _ && (console.group ? (d.header = ["%credux-undo", "font-style: italic", "action", e.type], d.action = S("action", P.action, e), d.prev = S("prev history", P.prevState, t)) : (d.header = ["redux-undo action", e.type], d.action = ["action", e], d.prev = ["prev history", t]));
}
function a(e) {
  _ && (console.group ? d.next = S("next history", P.nextState, e) : d.next = ["next history", e], H());
}
function f(...e) {
  _ && (d.msgs = d.msgs.concat([...e, `
`]));
}
function j(e) {
  _ = e;
}
function m(e, t) {
  const n = T([], e, []);
  return t && (n._latestUnfiltered = null), n;
}
function I(e, t, n, s) {
  const l = e.past.length + 1;
  f("inserting", t), f("new free: ", n - l);
  const { past: i, _latestUnfiltered: o } = e, p = n && n <= l, r = i.slice(p ? 1 : 0), u = o != null ? [
    ...r,
    o
  ] : r;
  return T(u, t, [], s);
}
function A(e, t) {
  if (t < 0 || t >= e.future.length)
    return e;
  const { past: n, future: s, _latestUnfiltered: l } = e, i = [...n, l, ...s.slice(0, t)], o = s[t], p = s.slice(t + 1);
  return T(i, o, p);
}
function x(e, t) {
  if (t < 0 || t >= e.past.length)
    return e;
  const { past: n, future: s, _latestUnfiltered: l } = e, i = n.slice(0, t), o = [...n.slice(t + 1), l, ...s], p = n[t];
  return T(i, p, o);
}
function O(e, t) {
  return t > 0 ? A(e, t - 1) : t < 0 ? x(e, e.past.length + t) : e;
}
function J(e, t) {
  return t.indexOf(e) > -1 ? e : !e;
}
function C(e, t = {}) {
  j(t.debug);
  const n = {
    limit: void 0,
    filter: () => !0,
    groupBy: () => null,
    undoType: c.UNDO,
    redoType: c.REDO,
    jumpToPastType: c.JUMP_TO_PAST,
    jumpToFutureType: c.JUMP_TO_FUTURE,
    jumpType: c.JUMP,
    neverSkipReducer: !1,
    ignoreInitialState: !1,
    syncFilter: !1,
    ...t,
    initTypes: U(t.initTypes, ["@@redux-undo/INIT"]),
    clearHistoryType: U(
      t.clearHistoryType,
      [c.CLEAR_HISTORY]
    )
  }, s = n.neverSkipReducer ? (i, o, ...p) => ({
    ...i,
    present: e(i.present, o, ...p)
  }) : (i) => i;
  let l;
  return (i = l, o = {}, ...p) => {
    h(o, i);
    let r = i;
    if (!l)
      if (f("history is uninitialized"), i === void 0) {
        const g = e(i, { type: "@@redux-undo/CREATE_HISTORY" }, ...p);
        return r = m(
          g,
          n.ignoreInitialState
        ), f("do not set initialState on probe actions"), a(r), r;
      } else
        E(i) ? (r = l = n.ignoreInitialState ? i : T(
          i.past,
          i.present,
          i.future
        ), f(
          "initialHistory initialized: initialState is a history",
          l
        )) : (r = l = m(
          i,
          n.ignoreInitialState
        ), f(
          "initialHistory initialized: initialState is not a history",
          l
        ));
    let u;
    switch (o.type) {
      case void 0:
        return r;
      case n.undoType:
        return u = O(r, -1), f("perform undo"), a(u), s(u, o, ...p);
      case n.redoType:
        return u = O(r, 1), f("perform redo"), a(u), s(u, o, ...p);
      case n.jumpToPastType:
        return u = x(r, o.index), f(`perform jumpToPast to ${o.index}`), a(u), s(u, o, ...p);
      case n.jumpToFutureType:
        return u = A(r, o.index), f(`perform jumpToFuture to ${o.index}`), a(u), s(u, o, ...p);
      case n.jumpType:
        return u = O(r, o.index), f(`perform jump to ${o.index}`), a(u), s(u, o, ...p);
      case J(o.type, n.clearHistoryType):
        return u = m(r.present, n.ignoreInitialState), f("perform clearHistory"), a(u), s(u, o, ...p);
      default:
        if (u = e(
          r.present,
          o,
          ...p
        ), n.initTypes.some((y) => y === o.type))
          return f("reset history due to init action"), a(l), l;
        if (r._latestUnfiltered === u)
          return r;
        if (typeof n.filter == "function" && !n.filter(
          o,
          u,
          r
        )) {
          const y = T(
            r.past,
            u,
            r.future,
            r.group
          );
          return n.syncFilter || (y._latestUnfiltered = r._latestUnfiltered), f("filter ignored action, not storing it in past"), a(y), y;
        }
        const g = n.groupBy(o, u, r);
        if (g != null && g === r.group) {
          const y = T(
            r.past,
            u,
            r.future,
            r.group
          );
          return f("groupBy grouped the action with the previous action"), a(y), y;
        }
        return r = I(r, u, n.limit, g), f("inserted new state into history"), a(r), r;
    }
  };
}
export {
  M as ActionCreators,
  c as ActionTypes,
  w as combineFilters,
  C as default,
  D as excludeAction,
  B as groupByActionTypes,
  v as includeAction,
  E as isHistory,
  T as newHistory,
  U as parseActions
};
