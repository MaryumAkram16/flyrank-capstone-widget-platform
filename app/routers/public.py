from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories import widgets_repo
from app.schemas import ChallengeOut, WidgetConfigOut
from app.services import pow as pow_service

router = APIRouter(tags=["public"])

# Bumped on every real release of the bundle. A new value here means a new
# URL (/widget/{version}.js), so browsers that cached the old immutable
# bundle simply never see the new one until the customer re-pastes the
# updated snippet — the standard "versioned bundle" cache-busting pattern.
CURRENT_BUNDLE_VERSION = "v1"


# Kept as a plain string bundle for the capstone — a real build step
# (esbuild/rollup) would generate this; see the brief's stretch goals.
_WIDGET_JS = """
(function () {
  var script = document.currentScript;
  var id = new URL(script.src).searchParams.get("id");
  if (!id) return;

  var apiBase = new URL(script.src).origin;

  // Proof-of-work solver: brute-forces a solution string such that
  // sha256(salt + solution) starts with `difficulty` zero hex chars. A real
  // browser does this in milliseconds via Web Crypto; a naive script bot
  // that just POSTs to /submissions directly has no solution at all.
  function toHex(buffer) {
    var bytes = new Uint8Array(buffer);
    var hex = "";
    for (var i = 0; i < bytes.length; i++) {
      hex += bytes[i].toString(16).padStart(2, "0");
    }
    return hex;
  }

  async function solveChallenge(salt, difficulty) {
    var prefix = "0".repeat(difficulty);
    var counter = 0;
    while (true) {
      var candidate = String(counter);
      var encoded = new TextEncoder().encode(salt + candidate);
      var digestBuffer = await crypto.subtle.digest("SHA-256", encoded);
      if (toHex(digestBuffer).startsWith(prefix)) {
        return candidate;
      }
      counter++;
    }
  }

  fetch(apiBase + "/widgets/" + id + "/config")
    .then(function (r) { return r.json(); })
    .then(function (cfg) { renderWidget(cfg); })
    .catch(function () { /* config fetch failed -- fail silently, no widget shown */ });

  function renderWidget(cfg) {
    var container = document.createElement("div");
    container.className = "fr-widget fr-widget-" + cfg.type;

    var title = document.createElement("h3");
    title.textContent = cfg.title;
    container.appendChild(title);

    if (cfg.description) {
      var desc = document.createElement("p");
      desc.textContent = cfg.description;
      container.appendChild(desc);
    }

    var form = document.createElement("form");

    cfg.fields.forEach(function (f) {
      var label = document.createElement("label");
      label.textContent = f.label;
      var input = f.type === "textarea" ? document.createElement("textarea")
                : document.createElement("input");
      if (f.type !== "textarea") input.type = f.type === "checkbox" ? "checkbox" : "text";
      input.name = f.name;
      if (f.required) input.required = true;
      label.appendChild(input);
      form.appendChild(label);
    });

    // Honeypot -- hidden via CSS, never shown to a real visitor.
    var honeypot = document.createElement("input");
    honeypot.type = "text";
    honeypot.name = "website";
    honeypot.style.cssText = "position:absolute;left:-9999px;";
    honeypot.tabIndex = -1;
    honeypot.autocomplete = "off";
    form.appendChild(honeypot);

    var button = document.createElement("button");
    button.type = "submit";
    button.textContent = cfg.button_text;
    form.appendChild(button);

    var status = document.createElement("p");
    status.className = "fr-widget-status";

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      button.disabled = true;
      status.textContent = "Verifying\u2026";

      var data = {};
      cfg.fields.forEach(function (f) {
        var el = form.elements[f.name];
        data[f.name] = f.type === "checkbox" ? String(el.checked) : el.value;
      });

      fetch(apiBase + "/widgets/" + id + "/challenge")
        .then(function (r) { return r.json(); })
        .then(function (challenge) {
          return solveChallenge(challenge.salt, challenge.difficulty).then(function (solution) {
            return fetch(apiBase + "/submissions", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                widget_id: id,
                data: data,
                website: form.elements["website"].value,
                challenge_id: challenge.challenge_id,
                solution: solution,
              }),
            });
          });
        })
        .then(function (r) {
          status.textContent = r.ok ? "Thanks!" : "Something went wrong.";
          button.disabled = false;
        })
        .catch(function () {
          status.textContent = "Something went wrong.";
          button.disabled = false;
        });
    });

    container.appendChild(form);
    container.appendChild(status);
    document.body.appendChild(container);
  }
})();
"""


@router.get("/widget/{version}.js")
def get_versioned_widget_bundle(version: str):
    """The real embed target: /widget/v1.js. Immutable forever — a new
    release ships as /widget/v2.js, never by mutating this URL's content."""
    return Response(
        content=_WIDGET_JS,
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.get("/widget.js")
def get_widget_bundle():
    """Convenience alias to the current version, kept short-cached so a
    customer who pasted the unversioned URL still picks up releases —
    version-pinned integrations should use /widget/{version}.js instead."""
    return Response(
        content=_WIDGET_JS,
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.get("/widgets/{widget_id}/config", response_model=WidgetConfigOut)
def get_widget_config(widget_id: str, response: Response, db: Session = Depends(get_db)):
    widget = widgets_repo.get_public(db, widget_id)
    if widget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")
    response.headers["Cache-Control"] = "public, max-age=60"
    response.headers["Access-Control-Allow-Origin"] = "*"
    return widget


@router.get("/widgets/{widget_id}/challenge", response_model=ChallengeOut)
def get_submission_challenge(widget_id: str, response: Response, db: Session = Depends(get_db)):
    """Issues a fresh proof-of-work challenge for this widget. The widget
    bundle calls this right before rendering the form so the solve can start
    immediately; never cached — every call must return a fresh, single-use
    challenge."""
    widget = widgets_repo.get_public(db, widget_id)
    if widget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Access-Control-Allow-Origin"] = "*"
    challenge = pow_service.issue_challenge(widget_id)
    return ChallengeOut(challenge_id=challenge.id, salt=challenge.salt, difficulty=challenge.difficulty)
