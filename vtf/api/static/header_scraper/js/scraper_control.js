(function () {
  "use strict";

  const config = window.HEADER_SCRAPER_CONFIG || {};
  const statusUrlTemplate = config.statusUrlTemplate || "";
  const pollIntervalMs = 3000;

  const statusLabels = {
    queued: "En file d'attente",
    running: "En cours",
    completed: "Terminé",
    failed: "Échoué / arrêté",
    idle: "Inactif",
  };

  function resolveStatusUrl(taskId) {
    return statusUrlTemplate.replace("__TASK_ID__", encodeURIComponent(taskId));
  }

  function getTrackedTaskId() {
    const params = new URLSearchParams(window.location.search);
    return params.get("task") || config.queryTaskId || config.activeTaskId || "";
  }

  function setButtonsActive(isActive) {
    const startBtn = document.getElementById("btn-start");
    const stopBtn = document.getElementById("btn-stop");
    if (startBtn) startBtn.disabled = isActive;
    if (stopBtn) stopBtn.disabled = !isActive;
  }

  function updateStatusPanel(data) {
    const badge = document.getElementById("job-status-badge");
    const label = document.getElementById("job-status-label");
    const details = document.getElementById("job-status-details");
    const summary = document.getElementById("job-summary");
    const stopTaskId = document.getElementById("stop-job-id");
    const panel = document.getElementById("job-status-panel");

    if (!badge || !label || !details || !summary) return;

    const status = data.status || "idle";
    const isActive = Boolean(data.isActive);

    badge.dataset.status = status;
    badge.textContent = statusLabels[status] || status;
    label.textContent = "";
    if (data.taskId) {
      label.append("Tâche active : ");
      const strong = document.createElement("strong");
      strong.id = "job-id-display";
      strong.textContent = data.taskId;
      label.append(strong);
    } else {
      label.textContent = "Aucun scraping en cours.";
    }

    details.innerHTML = "";
    if (data.taskId) {
      const rows = [
        ["Cible", (data.targetType || "") + " — " + (data.targetId || "")],
      ];
      rows.forEach(function (row) {
        const wrap = document.createElement("div");
        const dt = document.createElement("dt");
        const dd = document.createElement("dd");
        dt.textContent = row[0];
        dd.textContent = row[1];
        wrap.appendChild(dt);
        wrap.appendChild(dd);
        details.appendChild(wrap);
      });
    }

    if (data.summary) {
      const parts = [];
      // Single-language result (task_scrape_header_banner_language).
      if (data.summary.status) {
        parts.push("Statut : " + data.summary.status);
      }
      // All-languages result (task_scrape_header_banner): {ok, results: [...]}.
      if (Array.isArray(data.summary.results)) {
        data.summary.results.forEach(function (r) {
          parts.push((r.language || "") + " : " + (r.status || ""));
        });
      }
      if (data.summary.error) {
        parts.push("Message : " + data.summary.error);
      }
      summary.textContent = parts.join(" · ");
    } else {
      summary.textContent = "";
    }

    if (stopTaskId) stopTaskId.value = data.taskId || "";
    if (panel) panel.classList.toggle("job-status-idle", !data.taskId || !isActive);
    setButtonsActive(isActive);
  }

  function pollTaskStatus(taskId) {
    if (!taskId) {
      updateStatusPanel({ status: "idle", isActive: false });
      return;
    }

    fetch(resolveStatusUrl(taskId), {
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    })
      .then(function (response) {
        if (!response.ok) throw new Error("status poll failed");
        return response.json();
      })
      .then(function (data) {
        updateStatusPanel(data);
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

  function initTargetToggle() {
    const languageField = document.getElementById("field-language");
    const radios = document.querySelectorAll("[data-target-toggle]");

    function applyTarget(target) {
      if (!languageField) return;
      languageField.classList.toggle("scraper-hidden", target !== "language");
    }

    radios.forEach(function (radio) {
      radio.addEventListener("change", function () {
        if (radio.checked) applyTarget(radio.value);
      });
    });

    const checked = document.querySelector("[data-target-toggle]:checked");
    applyTarget(checked ? checked.value : "language");
  }

  document.addEventListener("DOMContentLoaded", function () {
    initTargetToggle();
    const taskId = getTrackedTaskId();
    pollTaskStatus(taskId);
  });
})();
