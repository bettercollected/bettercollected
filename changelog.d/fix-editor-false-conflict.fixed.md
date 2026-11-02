- The form editor no longer says a form "changed elsewhere" after your own edit. When the answer to an
  autosave got lost (a dropped connection or a gateway timeout) the editor sent the edit again, and the
  server, which had already stored it, took that for a change made in another tab. The editor now sends
  such a save again first, and the server answers a save that its draft already contains with the stored
  draft instead of a conflict. A save over a draft that really changed elsewhere is still refused.
