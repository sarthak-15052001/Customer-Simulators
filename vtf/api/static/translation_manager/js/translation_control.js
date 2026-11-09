(function () {
  "use strict";

  const config = window.TRANSLATION_MANAGER_CONFIG || {};
  const statusUrlTemplate = config.statusUrlTemplate || "";
  const pollIntervalMs = 3000;

  const statusLabels = {
    queued: "En file d'attente",
    running: "En cours",
    completed: "Terminé",
    failed: "Échoué",
    idle: "Inactif",
  };

  function resolveStatusUrl(taskId) {
    return statusUrlTemplate.replace("__TASK_ID__", encodeURIComponent(taskId));
  }

  function updateBadge(data) {
    const badge = document.getElementById("translation-status-badge");
    const summary = document.getElementById("translation-summary");
    if (!badge) return;

    const status = data.status || "idle";
    badge.dataset.status = status;
    badge.textContent = statusLabels[status] || status;

    if (summary) {
      if (data.summary && data.summary.error) {
        summary.textContent = "Message : " + data.summary.error;
      } else if (data.summary && typeof data.summary.queued_sources === "number") {
        summary.textContent = data.summary.queued_sources + " source(s) mise(s) en file.";
      } else {
        summary.textContent = "";
      }
    }
  }

  function pollTaskStatus(taskId) {
    if (!taskId || taskId.indexOf("batch-") === 0) return;

    fetch(resolveStatusUrl(taskId), {
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    })
      .then(function (response) {
        if (!response.ok) throw new Error("status poll failed");
        return response.json();
      })
      .then(function (data) {
        updateBadge(data);
        if (data.isActive) {
          window.setTimeout(function () {
            pollTaskStatus(taskId);
          }, pollIntervalMs);
        }
      })
      .catch(function () {
        window.setTimeout(function () {
          pollTaskStatus(taskId);
        }, pollIntervalMs);
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (config.activeTaskId) {
      pollTaskStatus(config.activeTaskId);
    }
  });
})();
