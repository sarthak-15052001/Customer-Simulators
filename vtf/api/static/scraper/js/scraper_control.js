(function () {
  "use strict";

  const config = window.SCRAPER_CONFIG || {};
  const statusUrlTemplate = config.statusUrlTemplate || "";
  const pollIntervalMs = 3000;

  const statusLabels = {
    queued: "En file d'attente",
    running: "En cours",
    completed: "Terminé",
    failed: "Échoué / arrêté",
    idle: "Inactif",
  };

  function resolveStatusUrl(jobId) {
    return statusUrlTemplate.replace("__JOB_ID__", encodeURIComponent(jobId));
  }

  function getTrackedJobId() {
    const params = new URLSearchParams(window.location.search);
    return params.get("job") || config.queryJobId || config.activeJobId || "";
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
    const stopJobId = document.getElementById("stop-job-id");
    const panel = document.getElementById("job-status-panel");

    if (!badge || !label || !details || !summary) return;

    const status = data.status || "idle";
    const isActive = Boolean(data.isActive);

    badge.dataset.status = status;
    badge.textContent = statusLabels[status] || status;
    label.innerHTML = data.jobId
      ? 'Job actif : <strong id="job-id-display">' + data.jobId + "</strong>"
      : "Aucun scraping en cours.";

    details.innerHTML = "";
    if (data.jobId) {
      const rows = [
        ["Cible", (data.targetType || "") + " — " + (data.targetId || "")],
        ["Sources", (data.sources || []).join(", ")],
        ["Rayon", (data.radiusKm || "") + " km"],
        ["Résultats max", data.maxResults || ""],
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
      if (typeof data.summary.totalNew === "number") {
        parts.push("Nouveaux : " + data.summary.totalNew);
      }
      if (typeof data.summary.readyForReview === "number") {
        parts.push("À revoir : " + data.summary.readyForReview);
      }
      if (typeof data.summary.totalDuplicates === "number") {
        parts.push("Doublons : " + data.summary.totalDuplicates);
      }
      if (data.summary.error) {
        parts.push("Message : " + data.summary.error);
      }
      summary.textContent = parts.join(" · ");
    } else {
      summary.textContent = "";
    }

    if (stopJobId) stopJobId.value = data.jobId || "";
    if (panel) panel.classList.toggle("job-status-idle", !data.jobId || !isActive);
    setButtonsActive(isActive);
  }

  function pollJobStatus(jobId) {
    if (!jobId) {
      updateStatusPanel({ status: "idle", isActive: false });
      return;
    }

    fetch(resolveStatusUrl(jobId), {
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
            pollJobStatus(jobId);
          }, pollIntervalMs);
        }
      })
      .catch(function () {
        window.setTimeout(function () {
          pollJobStatus(jobId);
        }, pollIntervalMs);
      });
  }

  function initTargetToggle() {
    const villageField = document.getElementById("field-village");
    const regionField = document.getElementById("field-region");
    const radios = document.querySelectorAll("[data-target-toggle]");

    function applyTarget(target) {
      if (!villageField || !regionField) return;
      const isVillage = target === "village";
      villageField.classList.toggle("scraper-hidden", !isVillage);
      regionField.classList.toggle("scraper-hidden", isVillage);
    }

    radios.forEach(function (radio) {
      radio.addEventListener("change", function () {
        if (radio.checked) applyTarget(radio.value);
      });
    });

    const checked = document.querySelector("[data-target-toggle]:checked");
    applyTarget(checked ? checked.value : "village");
  }

  document.addEventListener("DOMContentLoaded", function () {
    initTargetToggle();
    const jobId = getTrackedJobId();
    pollJobStatus(jobId);
  });
})();
