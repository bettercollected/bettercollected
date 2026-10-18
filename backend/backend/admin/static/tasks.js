/* Live progress for a run page. Optional: the page works without it (Refresh link).
   Polls the run's JSON every 2 seconds while it is queued or running, writes
   only with textContent (never markup), and reloads once when the run ends so
   the result and any refusal are shown by the server-rendered page. */
(function () {
  "use strict";
  var box = document.getElementById("live");
  if (!box || box.getAttribute("data-terminal") === "yes") { return; }
  var runId = box.getAttribute("data-run-id");
  if (!/^[0-9a-f-]{36}$/.test(runId || "")) { return; }
  var follow = box.getAttribute("data-follow") === "yes";
  var last = parseInt(box.getAttribute("data-last-seq"), 10) || 0;
  var indicator = document.getElementById("live-indicator");
  var stateEl = document.getElementById("state");
  var bar = document.getElementById("progress");
  var barText = document.getElementById("progress-text");
  var rows = document.getElementById("event-rows");
  var failures = 0;
  var timer = null;

  function show(text) {
    if (indicator) { indicator.hidden = false; indicator.textContent = text; }
  }

  function cell(row, text, code) {
    var td = document.createElement("td");
    if (code) {
      var c = document.createElement("code");
      c.textContent = text;
      td.appendChild(c);
    } else {
      td.textContent = text;
    }
    row.appendChild(td);
  }

  function addEvent(e) {
    if (!rows || !follow) { return; }
    var none = document.getElementById("no-events");
    if (none) { none.remove(); }
    var tr = document.createElement("tr");
    var counts = Object.keys(e.counts || {}).map(function (k) { return k + "=" + e.counts[k]; }).join(", ");
    cell(tr, String(e.seq), false);
    cell(tr, String(e.at).replace("T", " ").slice(0, 19) + " UTC", false);
    cell(tr, e.code, true);
    cell(tr, counts || "-", false);
    cell(tr, (e.ids || []).join(", ") || "-", false);
    cell(tr, e.error_class || "-", false);
    rows.appendChild(tr);
    last = Math.max(last, e.seq);
  }

  function apply(data) {
    if (stateEl) { stateEl.textContent = data.state; }
    if (bar && typeof data.percent === "number") {
      bar.hidden = false;
      bar.value = data.percent;
    }
    if (barText && typeof data.done === "number") {
      barText.textContent = typeof data.total === "number" ? data.done + " / " + data.total : String(data.done);
    }
    (data.events || []).forEach(addEvent);
    if (data.terminal) {
      show("Finished");
      window.location.reload();
      return false;
    }
    return true;
  }

  function poll() {
    var req = new XMLHttpRequest();
    req.open("GET", "/api/tasks/runs/" + runId + "?after=" + last);
    req.setRequestHeader("Accept", "application/json");
    req.onload = function () {
      var keep = true;
      if (req.status === 200) {
        failures = 0;
        try { keep = apply(JSON.parse(req.responseText)); } catch (err) { failures += 1; }
        if (keep) { show("Live"); }
      } else {
        failures += 1;
      }
      schedule(keep);
    };
    req.onerror = function () { failures += 1; schedule(true); };
    req.send();
  }

  function schedule(keep) {
    if (!keep) { return; }
    if (failures >= 5) { show("Paused: use Refresh"); return; }
    timer = window.setTimeout(poll, 2000);
  }

  show("Live");
  timer = window.setTimeout(poll, 1000);
}());
